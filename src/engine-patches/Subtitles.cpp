// karin: Quake 4 简体中文汉化项目新增 —— 语音字幕（Apex/HL2 风格整块面板）
// 面板底部锚定，新行从下方顶入，高度平滑伸缩，行淡入淡出
// GUI 资产: guis/subtitles.gui

#include "../idlib/precompiled.h"
#pragma hdrstop

#include "Game_local.h"
#include "Sound.h"
#include "Subtitles.h"

idCVar harm_g_subtitles( "harm_g_subtitles", "1", CVAR_GAME | CVAR_BOOL | CVAR_ARCHIVE, "enable voice subtitles" );
idCVar harm_g_subtitleHoldTime( "harm_g_subtitleHoldTime", "700", CVAR_GAME | CVAR_INTEGER | CVAR_ARCHIVE, "extra time(ms) subtitle stays after voice ends" );
idCVar harm_g_subtitleMinTime( "harm_g_subtitleMinTime", "1500", CVAR_GAME | CVAR_INTEGER | CVAR_ARCHIVE, "minimum time(ms) a subtitle stays" );
idCVar harm_g_subtitleTest( "harm_g_subtitleTest", "", CVAR_GAME, "debug: push a test subtitle line" );
idCVar harm_g_subtitleDebug( "harm_g_subtitleDebug", "0", CVAR_GAME | CVAR_BOOL, "debug: print subtitle add/skip decisions to console" );
idCVar harm_g_subtitlePVSCheck( "harm_g_subtitlePVSCheck", "1", CVAR_GAME | CVAR_BOOL | CVAR_ARCHIVE, "hide subtitles of speakers outside player PVS (occluded)" );

// 近距离豁免：此距离（游戏单位）内即使隔墙（不在 PVS）也显示字幕
static const float SUB_PVS_NEAR_DIST = 240.0f;

// 面板布局（640x480 虚拟坐标）；2026-07-17 用户要求：面板上移且缩窄
// （与 guis/subtitles.gui 的 rect 及 SUB_TEXT_W 联动，改一处须同步三处）
static const float SUB_BOTTOM	= 410.0f;	// 面板底边（原 428）
static const float SUB_ROW_H	= 13.0f;	// 行高
static const float SUB_PAD		= 4.0f;		// 上下留白
// 字幕在面板里的额外 y 偏移（视觉居中微调）：v1.0.7 曾用 1.0 补偿 CJK drop 偏顶，
// 但 v1.0.9 用户反馈"字幕相较背景偏下" → 撤回为 0（chain 独立 canonical 后 lowpixel
// 与 marine 同源 chain=marine（marine 现在是 canonical），drop 度量与之前不同）。
static const float SUB_ROW_ADJ	= 0.0f;
static const int   FADE_IN_MS	= 150;
static const int   FADE_OUT_MS	= 300;

rvSubtitles gameSubtitles;

// —— 行宽度量（与引擎 DrawText 同款推进公式：xSkip * useScale）——
// 首次使用时从字幕 GUI 同款 fontdat 读取真实字形步进，文件缺失时退回估值
static const float SUB_TEXT_W		= 362.0f;					// 行像素预算（gui 文本区宽 368，留行首禁则并入余量）
// 2026-07-17 字幕改用 24 号字库同尺寸渲染：gui_smallFontLimit 置 0（启动脚本/
// 配置下发）后 textscale 0.19 落入 24 号档，useScale=0.19×48/24=0.38，屏显
// 尺寸不变、度量分辨率翻倍——fontdat 步进是整数，12 号下拉丁字母 4~6px 的
// ±0.5 舍入误差屏显达 ±1.1px（"gg"/"ss" 忽缝忽挤的根因），24 号相对误差减半
static const float SUB_USE_SCALE	= 0.19f * 48.0f / 24.0f;	// textscale 0.19 → 24 号字库（smallFontLimit=0）
static const char *SUB_FONT_DAT		= "fonts/chinese/lowpixel_24.fontdat";
static const float SUB_ASCII_FALLBACK	= 15.0f;				// 估值：ASCII 平均步进（字库像素）
static const float SUB_WIDE_FALLBACK	= 26.0f;				// 估值：全角步进（字库像素）

static bool		subMetricsTried = false;
static float	subAsciiAdv[128];
static byte *	subWideAdv = NULL;		// charcode → xSkip（字库像素，0=缺字形）
static int		subWideNum = 0;

// 声音 shader 名 → 说话人 映射（speaker_map.txt，build_lang.py 生成）
// speaker 实体/无线电播放的语音：有映射=角色台词(带角色名)，无映射=环境广播("广播"/"无线电")
static idDict	subSpeakerMap;
static bool		subSpeakerMapLoaded = false;
static void		SUB_LoadSpeakerMap( void );

/*
================
SUB_LoadFontMetrics

fontdat 布局（tr_font_tools.cpp）：
Q4 基础段 256 × 9 float（imageWidth,imageHeight,xSkip,pitch,top,s,t,s2,t2）+ 5 float；
宽字库扩展段 magic/version/numFiles/width/height + numIndexes + indexes[] + numGlyphs
+ 每字形 9 float + 32 字节贴图名 = 68 字节。
================
*/
static void SUB_LoadFontMetrics( void ) {
	subMetricsTried = true;
	int i;
	for ( i = 0; i < 128; i++ ) {
		subAsciiAdv[i] = SUB_ASCII_FALLBACK;
	}

	void *buf = NULL;
	int len = fileSystem->ReadFile( SUB_FONT_DAT, &buf );
	if ( len <= 0 || !buf ) {
		gameLocal.Warning( "rvSubtitles: %s not found, using fallback metrics", SUB_FONT_DAT );
		return;
	}
	const byte *p = ( const byte * )buf;

	const int baseSize = 256 * 36 + 20;
	if ( len >= baseSize ) {
		for ( i = 32; i < 127; i++ ) {
			float v;
			memcpy( &v, p + i * 36 + 2 * 4, sizeof( v ) );
			if ( v > 0.0f && v < 64.0f ) {
				subAsciiAdv[i] = v;
			}
		}
	}

	int off = baseSize + 20;
	int numIdx = 0;
	if ( len >= off + 4 ) {
		memcpy( &numIdx, p + off, 4 );
		off += 4;
	}
	if ( numIdx > 0 && numIdx <= 0x110000 && len >= off + numIdx * 4 + 4 ) {
		const byte *idxTable = p + off;
		off += numIdx * 4;
		int numGlyphs = 0;
		memcpy( &numGlyphs, p + off, 4 );
		off += 4;
		if ( numGlyphs > 0 && len >= off + numGlyphs * 68 ) {
			subWideAdv = new byte[numIdx];
			memset( subWideAdv, 0, numIdx );
			for ( i = 0; i < numIdx; i++ ) {
				int gi;
				memcpy( &gi, idxTable + i * 4, 4 );
				if ( gi >= 0 && gi < numGlyphs ) {
					float v;
					memcpy( &v, p + off + gi * 68 + 2 * 4, sizeof( v ) );
					int skip = ( int )v;
					subWideAdv[i] = ( byte )( ( skip < 0 ) ? 0 : ( ( skip > 255 ) ? 255 : skip ) );
				}
			}
			subWideNum = numIdx;
		}
	}
	fileSystem->FreeFile( buf );
}

/*
================
SUB_CharAdvance

单字符屏幕推进（640x480 虚拟像素）
================
*/
static float SUB_CharAdvance( unsigned int cp ) {
	float adv;
	if ( cp < 128 ) {
		adv = subAsciiAdv[cp];
	} else if ( subWideAdv && cp < ( unsigned int )subWideNum && subWideAdv[cp] ) {
		adv = subWideAdv[cp];
	} else {
		adv = SUB_WIDE_FALLBACK;
	}
	return adv * SUB_USE_SCALE;
}

/*
================
SUB_LoadSpeakerMap

加载声音 shader 名 → 说话人 映射（speaker_map.txt，build_lang.py 生成）。
格式：每行 "shader\tspeaker"，# 开头为注释。
用于区分 speaker 实体/无线电播放的是角色台词还是环境广播。
================
*/
static void SUB_LoadSpeakerMap( void ) {
	subSpeakerMapLoaded = true;
	void *buf = NULL;
	int len = fileSystem->ReadFile( "speaker_map.txt", &buf );
	if ( len <= 0 || !buf ) {
		return;
	}
	idStr data( ( const char * )buf );
	fileSystem->FreeFile( buf );
	int start = 0;
	while ( start < data.Length() ) {
		int end = data.Find( '\n', start );
		if ( end < 0 ) end = data.Length();
		idStr line = data.Mid( start, end - start );
		start = end + 1;
		line.StripTrailingWhitespace();
		if ( !line.Length() || line[0] == '#' ) continue;
		int tab = line.Find( '\t' );
		if ( tab < 0 ) continue;
		idStr shader = line.Left( tab );
		idStr name = line.Right( line.Length() - tab - 1 );
		shader.StripTrailingWhitespace();
		name.StripLeading( ' ' );
		if ( shader.Length() && name.Length() ) {
			subSpeakerMap.Set( shader, name );
		}
	}
}

/*
================
rvSubtitles::rvSubtitles
================
*/
rvSubtitles::rvSubtitles( void ) {
	numLines = 0;
	smoothH = 0.0f;
	lastDrawTime = 0;
}

/*
================
rvSubtitles::Clear
================
*/
void rvSubtitles::Clear( void ) {
	int i;
	for ( i = 0; i < MAX_SUBTITLE_LINES; i++ ) {
		lines[i].text.Clear();
		lines[i].startTime = 0;
		lines[i].endTime = 0;
	}
	numLines = 0;
	smoothH = 0.0f;
}

/*
================
rvSubtitles::AddLine
================
*/
void rvSubtitles::AddLine( const char *text, int endTime, subColor_t color ) {
	// 满员时挤掉最旧一条
	if ( numLines == MAX_SUBTITLE_LINES ) {
		int i;
		for ( i = 1; i < MAX_SUBTITLE_LINES; i++ ) {
			lines[i - 1] = lines[i];
		}
		numLines--;
	}

	subLine_t &sl = lines[numLines++];
	sl.text = text;
	sl.startTime = gameLocal.time;
	sl.endTime = endTime;
	sl.color = color;
}

/*
================
rvSubtitles::Sanitize

台词源串（transcribe text）里混有录音标注遗留物：
{furrow}/{idle} 等情绪标记、标记剥离后可能出现的连续空格。
这些只服务于口型/表情管线，展示前一律清理。
================
*/
void rvSubtitles::Sanitize( idStr &text ) {
	// 剥离 {…} 标记（不跨行，无嵌套）
	int lb;
	while ( ( lb = text.Find( '{' ) ) >= 0 ) {
		int rb = text.Find( '}', lb + 1 );
		if ( rb < 0 ) {
			break;
		}
		text = text.Left( lb ) + text.Right( text.Length() - rb - 1 );
	}

	// 折叠连续空格为单个
	idStr out;
	int i;
	bool lastSpace = false;
	for ( i = 0; i < text.Length(); i++ ) {
		if ( text[i] == ' ' ) {
			if ( lastSpace ) {
				continue;
			}
			lastSpace = true;
		} else {
			lastSpace = false;
		}
		out.Append( text[i] );
	}
	out.StripLeading( ' ' );
	out.StripTrailingWhitespace();
	text = out;
}

/*
================
rvSubtitles::IsAudible

说话点对玩家是否可听：
1. 过场演出 / 无关联声音 / 玩家自己说话 → 一律可听
2. 面向玩家的全局 VO（无线电类）→ 可听
3. 距离超出声音 shader 的 maxDistance（Q4 声音距离为游戏单位）→ 不可听
4. 近距离豁免外、说话实体不在玩家 PVS（隔墙/隔门）→ 不可听
================
*/
bool rvSubtitles::IsAudible( idEntity *bodyEnt, const idSoundShader *shader ) const {
	if ( !bodyEnt || !shader ) {
		return true;
	}
	// 过场期间过滤环境广播(speaker 实体)的字幕乱入,
	// 但保留剧情实体(idAI/idAFAttachment 等)的对白字幕。
	// 旧逻辑(2026-07-31)一刀切拦所有非 cinematic 实体,导致 Voss 被抓等
	// 过场对白(func_animate/head attachment 无 cinematic 标志)被误杀。
	// (2026-08-01 修复)
	if ( gameLocal.inCinematic ) {
		if ( bodyEnt->IsType( idSound::GetClassType() ) && !bodyEnt->cinematic ) {
			if ( harm_g_subtitleDebug.GetBool() ) {
				gameLocal.Printf( "[SUB] skip (non-cinematic speaker in cinematic): %s\n", bodyEnt->GetName() );
			}
			return false;
		}
		return true;
	}
	idPlayer *player = gameLocal.GetLocalPlayer();
	if ( !player || bodyEnt == player ) {
		return true;
	}
	if ( shader->IsVO_ForPlayer() ) {
		return true;
	}
	const soundShaderParms_t *parms = shader->GetParms();
	if ( parms->soundShaderFlags & SSF_GLOBAL ) {
		return true;
	}

	// 友军剧情语音按无线电对待（2026-07-17 用户反馈 Kovitch/Morris 台词缺字幕）：
	// 剧情脚本让队友在远处/隔墙处发言（实际经无线电传给玩家），距离与 PVS 门控
	// 会误拦——同队 actor 不做 PVS 门控，距离容差放宽 1.5 倍；
	// 敌军保留门控（防隔墙敌人喊话乱入字幕），距离留 1.15 容差纠正
	// 实体原点与声源发声点的偏差（实测 Morris 912 vs maxDistance 900 被误拦）
	bool friendly = false;
	if ( bodyEnt->IsType( idActor::GetClassType() ) ) {
		friendly = ( static_cast<idActor *>( bodyEnt )->team == player->team );
	}

	// speaker 实体（PA 广播）：广播系统设计为全设施覆盖，不应按距离/PVS 门控。
	// 环境音无 lipsync decl 不会进入此路径，只影响有 transcribe text 的 PA 广播。
	// (2026-08-01 用户反馈 Strogg 化后 Strogg 广播字幕时有时无：vo_pa_* 全部
	// 无 global 标志、maxDistance 仅 900，玩家走远后字幕被距离门控误拦)
	bool isSpeakerEnt = bodyEnt->IsType( idSound::GetClassType() );
	if ( isSpeakerEnt ) {
		return true;
	}

	float dist = ( player->GetPhysics()->GetOrigin() - bodyEnt->GetPhysics()->GetOrigin() ).LengthFast();
	float distLimit = parms->maxDistance * ( friendly ? 1.5f : 1.15f );
	if ( parms->maxDistance > 0.0f && dist > distLimit ) {
		if ( harm_g_subtitleDebug.GetBool() ) {
			gameLocal.Printf( "[SUB] skip (dist %.0f > limit %.0f): %s\n", dist, distLimit, bodyEnt->GetName() );
		}
		return false;
	}
	// speaker 实体已在上方提前 return，此处仅非 speaker 实体执行 PVS 门控
	if ( !friendly && harm_g_subtitlePVSCheck.GetBool() && dist > SUB_PVS_NEAR_DIST
	     && !gameLocal.InPlayerPVS( bodyEnt ) ) {
		if ( harm_g_subtitleDebug.GetBool() ) {
			gameLocal.Printf( "[SUB] skip (out of PVS, dist %.0f): %s\n", dist, bodyEnt->GetName() );
		}
		return false;
	}
	return true;
}

/*
================
rvSubtitles::Add

长台词按真实屏幕宽度拆行（fontdat 字形步进 × useScale，逐字符累计），
优先在空格处断行；拆出的各行共享同一个到期时间。
================
*/
void rvSubtitles::Add( const char *speaker, const char *text, int durationMs ) {
	if ( !harm_g_subtitles.GetBool() || !text || !text[0] ) {
		return;
	}
	// 未本地化的裸 #str_ 引用不显示
	if ( text[0] == '#' ) {
		if ( harm_g_subtitleDebug.GetBool() ) {
			gameLocal.Printf( "[SUB] skip (unlocalized): %s\n", text );
		}
		return;
	}

	idStr clean = text;
	Sanitize( clean );
	if ( !clean.Length() ) {
		return;
	}

	idStr full;
	if ( speaker && speaker[0] && speaker[0] != '#' ) {
		// 2026-07-18 用户要求：说话人与内容之间用全角中文冒号，不留空格
		// （原半角冒号 + 空格视觉突兀）。UTF-8 转义 \xEF\xBC\x9A = U+FF1A "："
		// MSVC 窄字符字面量按系统码页编译，必须写转义否则等价 GBK 字节序列。
		full = va( "%s\xEF\xBC\x9A%s", speaker, clean.c_str() );
	} else {
		full = clean;
	}

	// karin: 去重——同一字幕 300ms 内不重复添加（catch-all hook 可能与
	// LipSync/Sound 等 hook 同时触发同一声音）
	if ( numLines > 0 ) {
		subLine_t &last = lines[numLines - 1];
		if ( last.text == full && gameLocal.time - last.startTime < 300 ) {
			return;
		}
	}

	// 按说话人来源分配字幕配色(2026-08-01 用户要求：广播黄/无线电青/其余白,统一正常亮度)
	subColor_t color;
	if ( !speaker || !speaker[0] || speaker[0] == '#' ) {
		color = SUB_COLOR_NORMAL;	// 无说话人(无名环境音) — 白
	} else if ( idStr::Cmp( speaker, "\xE5\xB9\xBF\xE6\x92\xAD" ) == 0			// 广播
	        || idStr::Icmp( speaker, "PA" ) == 0
	        || strstr( speaker, "\xE6\x92\xAD\xE6\x8A\xA5" ) != NULL ) {		// 含"播报"(消毒室播报等地点播报)
		color = SUB_COLOR_BROADCAST;	// 广播类 — 黄
	} else if ( idStr::Cmp( speaker, "\xE6\x97\xA0\xE7\xBA\xBF\xE7\x94\xB5" ) == 0	// 无线电
	        || idStr::Icmp( speaker, "Radio" ) == 0 ) {
		color = SUB_COLOR_RADIO;		// 无线电 — 青
	} else {
		color = SUB_COLOR_NORMAL;	// 角色对白 — 白
	}

	if ( harm_g_subtitleDebug.GetBool() ) {
		gameLocal.Printf( "[SUB] show (%dms): %s\n", durationMs, full.c_str() );
	}

	int dur = durationMs;
	if ( dur < harm_g_subtitleMinTime.GetInteger() ) {
		dur = harm_g_subtitleMinTime.GetInteger();
	}
	int endTime = gameLocal.time + dur + harm_g_subtitleHoldTime.GetInteger();

	if ( !subMetricsTried ) {
		SUB_LoadFontMetrics();
	}

	const char *s = full.c_str();
	int len = full.Length();
	int pos = 0;
	while ( pos < len ) {
		float px = 0.0f;		// 本行累计屏幕宽
		int cut = pos;			// 硬切位置（字节）
		int lastSpace = -1;		// 行尾附近的空格断点（字节）
		int lastSpaceAny = -1;	// 任意位置最近空格（仅断词兜底用）
		int i = pos;
		while ( i < len ) {
			unsigned char c = s[i];
			int step = 1;
			unsigned int cp = c;
			if ( c >= 0xF0 ) {
				step = 4;
				cp = c & 0x07;
			} else if ( c >= 0xE0 ) {
				step = 3;
				cp = c & 0x0F;
			} else if ( c >= 0xC0 ) {
				step = 2;
				cp = c & 0x1F;
			}
			int k;
			for ( k = 1; k < step && i + k < len; k++ ) {
				cp = ( cp << 6 ) | ( s[i + k] & 0x3F );
			}
			float adv = SUB_CharAdvance( cp );
			if ( px + adv > SUB_TEXT_W ) {
				break;
			}
			px += adv;
			if ( c == ' ' ) {
				if ( px > SUB_TEXT_W * 0.92f ) {
					lastSpace = i;
				}
				lastSpaceAny = i;
			}
			i += step;
		}
		cut = i;
		if ( i < len ) {
			// 空格断点只在行尾附近（>70% 预算）才可取：中西文混排中前部的空格
			// （如 "瘫痪了 Strogg 的"）不能把整行断得过短。
			// 例外：溢出点落在英文单词中间时不硬切断词，退回任意位置的空格。
			bool midWord = i > pos &&
				isalnum( ( unsigned char )s[i] ) && isalnum( ( unsigned char )s[i - 1] );
			if ( lastSpace > pos ) {
				cut = lastSpace;
			} else if ( midWord && lastSpaceAny > pos ) {
				cut = lastSpaceAny;
			} else {
				// 行首禁则：中文标点不落行首，并入当前行（允许微超宽）
				static const char *noHead[] = {
					"\xEF\xBC\x8C", "\xE3\x80\x82", "\xEF\xBC\x81", "\xEF\xBC\x9F",
					"\xE3\x80\x81", "\xEF\xBC\x9B", "\xEF\xBC\x9A", "\xE2\x80\xA6",
					"\xE2\x80\x9D", "\xE3\x80\x8D", "\xEF\xBC\x89", NULL
				};	// ，。！？、；：…"」）
				bool absorbed = true;
				while ( absorbed ) {
					absorbed = false;
					int t;
					for ( t = 0; noHead[t]; t++ ) {
						int nlen = ( int )strlen( noHead[t] );
						if ( cut + nlen <= len && idStr::Cmpn( s + cut, noHead[t], nlen ) == 0 ) {
							cut += nlen;
							absorbed = true;
							break;
						}
					}
				}
			}
		}
		idStr seg = full.Mid( pos, cut - pos );
		seg.StripTrailingWhitespace();
		if ( seg.Length() ) {
			AddLine( seg.c_str(), endTime, color );
		}
		pos = cut;
		while ( pos < len && s[pos] == ' ' ) {
			pos++;
		}
	}
}

/*
================
rvSubtitles::LookupSpeaker

查声音 shader 名 → 说话人映射（speaker_map.txt）。供 Sound.cpp/Misc.cpp 挂钩区分
角色台词 vs 环境广播：有映射返回角色名，无映射返回 NULL（调用方 fallback 到默认前缀）。
================
*/
const char *rvSubtitles::LookupSpeaker( const char *shaderName ) {
	if ( !shaderName || !shaderName[0] ) return NULL;
	if ( !subSpeakerMapLoaded ) SUB_LoadSpeakerMap();
	const char *mapped = subSpeakerMap.GetString( shaderName );
	return ( mapped && mapped[0] ) ? mapped : NULL;
}

/*
================
rvSubtitles::AddFromEntity

从说话实体推断说话人名：
1. npc_name 有效且非占位名（Unnamed/未命名）→ 用之（本地化后）
2. 否则在实体名里识别已知角色（过场演出实体常以角色命名，如 cin_voss）
3. speaker 实体(广播/画面外角色)按 shader 名查 speaker_map → 角色名
4. 都失败 → 用 fallbackSpeaker（如"广播"）或留空
================
*/
void rvSubtitles::AddFromEntity( idEntity *bodyEnt, const char *text, int durationMs, const idSoundShader *shader, const char *fallbackSpeaker ) {
	static const char *knownSpeakers[] = {
		"cortez", "bidwell", "voss", "morris", "anderson", "rhodes",
		"sledge", "strauss", "kane", "walker", "hollenbeck", "scott",
		"mahler", "silverman", "harper", NULL
	};

	// 玩家听不到的说话不出字幕
	if ( !IsAudible( bodyEnt, shader ) ) {
		return;
	}

	idStr speaker;
	if ( bodyEnt ) {
		const char *rawName = bodyEnt->spawnArgs.GetString( "npc_name" );
		if ( rawName && rawName[0] ) {
			const char *loc = common->GetLocalizedString( rawName );
			// "未命名"必须用显式 UTF-8 转义：MSVC 把中文字面量按系统码页(GBK)编码，
			// 与 GetLocalizedString 返回的 UTF-8 字节永远不等，过滤会失效
			if ( loc && loc[0] && loc[0] != '#' &&
				 idStr::Icmp( loc, "Unnamed" ) != 0 &&
				 idStr::Cmp( loc, "\xE6\x9C\xAA\xE5\x91\xBD\xE5\x90\x8D" ) != 0 ) {
				speaker = loc;
			}
		}
		if ( !speaker.Length() ) {
			// 从实体名识别角色（大小写不敏感子串）
			idStr entName = bodyEnt->GetName();
			entName.ToLower();
			int i;
			for ( i = 0; knownSpeakers[i]; i++ ) {
				if ( entName.Find( knownSpeakers[i] ) >= 0 ) {
					speaker = knownSpeakers[i];
					speaker[0] = ( char )idStr::ToUpper( speaker[0] );
					break;
				}
			}
		}
		// 2026-07-18 用户要求字幕都有来源：无名友军 AI 兜底为"士兵"
		// （中文必须写 UTF-8 转义，MSVC GBK 码页坑）
		if ( !speaker.Length() && !fallbackSpeaker && bodyEnt->IsType( idActor::GetClassType() ) ) {
			idPlayer *pl = gameLocal.GetLocalPlayer();
			if ( pl && static_cast<idActor *>( bodyEnt )->team == pl->team ) {
				speaker = "\xE5\xA3\xAB\xE5\x85\xB5";	// 士兵
			}
		}
		// speaker 实体(广播 PA / 画面外角色如机甲检修 Morois)按 shader 名查角色映射:
		// 有映射=角色台词(如"Morois 下士",正常亮色), 无映射=环境广播(fallback"广播"+淡色)
		if ( !speaker.Length() && shader && bodyEnt->IsType( idSound::GetClassType() ) ) {
			const char *mapped = LookupSpeaker( shader->GetName() );
			if ( mapped ) speaker = mapped;
		}
	}
	if ( !speaker.Length() && fallbackSpeaker && fallbackSpeaker[0] ) {
		speaker = fallbackSpeaker;
	}

	Add( speaker.Length() ? speaker.c_str() : NULL, text, durationMs );
}

/*
================
rvSubtitles::Draw

整块半透明面板：底部固定，高度=行数，平滑伸缩；
行順序旧→新自上而下，新行从底部顶入。
================
*/
void rvSubtitles::Draw( void ) {
	int i;
	int now = gameLocal.time;

	// 调试注入
	if ( harm_g_subtitleTest.GetString()[0] ) {
		Add( NULL, harm_g_subtitleTest.GetString(), 4000 );
		harm_g_subtitleTest.SetString( "" );
	}

	// 过期或跨地图残留（startTime 超前于当前时间）的行删除
	for ( i = 0; i < numLines; ) {
		if ( lines[i].endTime <= now || lines[i].startTime > now ) {
			int j;
			for ( j = i + 1; j < numLines; j++ ) {
				lines[j - 1] = lines[j];
			}
			numLines--;
		} else {
			i++;
		}
	}

	if ( !harm_g_subtitles.GetBool() ) {
		return;
	}

	// 平滑高度（一阶趋近）
	int dt = now - lastDrawTime;
	lastDrawTime = now;
	if ( dt < 0 || dt > 200 ) {
		dt = 16;
	}
	float targetH = numLines ? ( numLines * SUB_ROW_H + SUB_PAD * 2.0f ) : 0.0f;
	float k = dt / 130.0f;
	if ( k > 1.0f ) {
		k = 1.0f;
	}
	smoothH += ( targetH - smoothH ) * k;
	if ( smoothH < 0.5f && !numLines ) {
		smoothH = 0.0f;
		return;		// 完全收起时不绘制
	}

	// 每帧按名查找（uiManager 内部有实例缓存）。绝不可把返回指针存成员跨图用：
	// 换图时 GUI 实例被释放重建，悬空指针 SetState/Redraw 写坏堆 → 概率性
	// c0000409 崩溃（2026-07-17 换图崩溃转储定位于此）
	idUserInterface *gui = uiManager->FindGui( "guis/subtitles.gui", true, false, true );
	if ( !gui ) {
		static bool warned = false;
		if ( !warned ) {
			warned = true;
			gameLocal.Warning( "rvSubtitles: guis/subtitles.gui not found, subtitles disabled" );
		}
		return;
	}

	float panelTop = SUB_BOTTOM - smoothH;
	float bgAlpha = 0.55f * ( smoothH / ( SUB_ROW_H + SUB_PAD * 2.0f ) );
	if ( bgAlpha > 0.55f ) {
		bgAlpha = 0.55f;
	}

	gui->SetStateFloat( "subBgY", panelTop );
	gui->SetStateFloat( "subBgH", smoothH );
	gui->SetStateFloat( "subBgA", bgAlpha );

	for ( i = 0; i < MAX_SUBTITLE_LINES; i++ ) {
		if ( i < numLines ) {
			// 行淡入淡出
			float aIn = ( now - lines[i].startTime ) / ( float )FADE_IN_MS;
			float aOut = ( lines[i].endTime - now ) / ( float )FADE_OUT_MS;
			float a = ( aIn < aOut ) ? aIn : aOut;
			if ( a > 1.0f ) {
				a = 1.0f;
			}
			if ( a < 0.0f ) {
				a = 0.0f;
			}
			// 行锚定面板底部：旧行过期删除时剩余行保持原位（只有背景板平滑收缩），
			// 面板生长期间取 max(静止位, 顶部滑入位) 保留新行从下方顶入的平滑效果
			float restY = SUB_BOTTOM - SUB_PAD - ( numLines - i ) * SUB_ROW_H + SUB_ROW_ADJ;
			float slideY = panelTop + SUB_PAD + i * SUB_ROW_H + SUB_ROW_ADJ;
			float rowY = ( restY > slideY ) ? restY : slideY;
			gui->SetStateString( va( "subText%d", i ), lines[i].text.c_str() );
			// 按配色类型设前景色 R/G/B(subtitles.gui forecolor 读这些变量)
			// 广播黄 / 无线电青 / 其余白;alpha 不再因类型打折(2026-08-01 用户要求统一亮度)
			float subR, subG, subB;
			switch ( lines[i].color ) {
				case SUB_COLOR_BROADCAST: subR = 1.0f;  subG = 0.80f; subB = 0.15f; break;
				case SUB_COLOR_RADIO:     subR = 0.35f; subG = 0.85f; subB = 1.0f;  break;
				default:                   subR = 0.95f; subG = 0.95f; subB = 0.95f; break;
			}
			gui->SetStateFloat( va( "subTxtR%d", i ), subR );
			gui->SetStateFloat( va( "subTxtG%d", i ), subG );
			gui->SetStateFloat( va( "subTxtB%d", i ), subB );
			gui->SetStateFloat( va( "subTxtA%d", i ), a * 0.97f );
			gui->SetStateFloat( va( "subRowY%d", i ), rowY );
		} else {
			gui->SetStateString( va( "subText%d", i ), "" );
			gui->SetStateFloat( va( "subTxtA%d", i ), 0.0f );
			gui->SetStateFloat( va( "subRowY%d", i ), SUB_BOTTOM );
		}
	}
	gui->Redraw( now );
}
