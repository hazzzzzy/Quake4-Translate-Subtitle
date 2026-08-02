// karin: Quake 4 简体中文汉化项目新增 —— HL 风格语音字幕
// 文本来源: rvDeclLipSync::GetTranscribeText()（经 GetLocalizedString 本地化）
#ifndef __GAME_SUBTITLES_H__
#define __GAME_SUBTITLES_H__

#define MAX_SUBTITLE_LINES	8

// 字幕配色类型：按说话人来源区分前景色（取代旧的 dimmed 二态淡色）
enum subColor_t {
	SUB_COLOR_NORMAL = 0,	// 角色对白 / 无名环境音 — 白
	SUB_COLOR_BROADCAST,	// Strogg广播(PA) — 黄
	SUB_COLOR_RADIO,		// 无线电 — 青
	SUB_COLOR_MAKRON,		// Makron — 紫
	SUB_COLOR_HUMANCAST		// 人类/舰船广播 — 绿
};

class idSoundShader;

class rvSubtitles {
public:
						rvSubtitles( void );

	void				Clear( void );
	// speaker 可为 NULL；durationMs 为语音时长（毫秒）
	void				Add( const char *speaker, const char *text, int durationMs );
	// 从说话实体推断说话人名后加入；shader 非 NULL 时做可听性门控；
	// fallbackSpeaker：推断不出名字时的兜底前缀（如 speaker 实体传"广播"）
	void				AddFromEntity( idEntity *bodyEnt, const char *text, int durationMs, const idSoundShader *shader = NULL, const char *fallbackSpeaker = NULL );
	// 查声音 shader 名 → 说话人映射（speaker_map.txt）。返回非空=角色台词（用角色名），
	// 返回 NULL=环境音（fallback 到"广播"/"无线电"默认前缀+淡色）。供 Sound.cpp/Misc.cpp 挂钩调用
	static const char *	LookupSpeaker( const char *shaderName );
	// 每帧在 idGameLocal::Draw 尾部调用
	void				Draw( void );

private:
	void				AddLine( const char *text, int endTime, subColor_t color );
	// 说话点相对玩家是否可听（距离超出声音衰减半径 / 近距离外不在 PVS 内则不可听）
	bool				IsAudible( idEntity *bodyEnt, const idSoundShader *shader ) const;
	// 剥离 {emotion} 标记并折叠多余空格
	static void			Sanitize( idStr &text );

	struct subLine_t {
		idStr			text;
		int				startTime;
		int				endTime;
		subColor_t		color;		// 字幕配色类型(角色白/广播黄/无线电青)
	};

	subLine_t			lines[MAX_SUBTITLE_LINES];
	int					numLines;
	// 注意：不得缓存 gui 指针跨地图使用——换图时 uiManager 释放重建 GUI 实例，
	// 缓存指针悬空导致堆损坏概率崩溃（c0000409，2026-07-17 转储定位），
	// Draw 内每帧按名 FindGui
	float				smoothH;
	int					lastDrawTime;
};

extern rvSubtitles		gameSubtitles;
extern idCVar			harm_g_subtitleDebug;

#endif /* !__GAME_SUBTITLES_H__ */
