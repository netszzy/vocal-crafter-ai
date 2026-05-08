"""
ccwebui 主入口
Gradio 三 Tab 界面：音色管理 / 语音生成 / 历史记录
"""

from __future__ import annotations

import base64
import html
from pathlib import Path
from urllib.parse import quote

import gradio as gr

from config import (
    MAX_REF_DURATION_SECS,
    OUTPUTS_DIR,
    PRELOAD_ASR_ON_START,
    REFS_DIR,
    SERVER_NAME,
    SERVER_PORT,
)
from voice_manager import VoiceManager
from task_manager import TaskManager
import audio_processor

# ============================================================
# 全局实例
# ============================================================

voice_mgr = VoiceManager()
task_mgr = TaskManager()

CSS = """
.gradio-container { max-width: 1100px !important; }
"""

INLINE_AUDIO_LIMIT_BYTES = 20 * 1024 * 1024

# ============================================================
# 工具函数
# ============================================================


def _table_data(raw) -> list[list]:
    """兼容 Gradio 5 Dataframe 值格式（dict 或 list）"""
    if isinstance(raw, dict) and "data" in raw:
        return raw["data"]
    return list(raw)


def _wav_to_html(wav_path: str | None) -> str:
    """Render an audio player without base64-loading large wav files."""
    if not wav_path or not Path(wav_path).exists():
        return '<div style="padding:10px;color:#888;">无音频</div>'
    try:
        path = Path(wav_path).resolve()
        size = path.stat().st_size
        size_mb = size / 1024 / 1024
        safe_name = html.escape(path.name)

        if size > INLINE_AUDIO_LIMIT_BYTES:
            file_url = f"/gradio_api/file={quote(path.as_posix(), safe='/:')}"
            return (
                f'<audio controls preload="metadata" style="width:100%;" '
                f'src="{file_url}"></audio>'
                f'<div style="font-size:12px;color:#888;margin-top:2px;">'
                f'{safe_name} ({size_mb:.1f} MB)</div>'
            )

        data = path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return (
            f'<audio controls style="width:100%;" '
            f'src="data:audio/wav;base64,{b64}"></audio>'
            f'<div style="font-size:12px;color:#888;margin-top:2px;">'
            f'{safe_name} ({size_mb:.1f} MB)</div>'
        )
    except Exception as e:
        return f'<div style="padding:10px;color:red;">加载失败: {e}</div>'


def _voice_table_rows() -> list[list[str]]:
    voices = voice_mgr.list_voices()
    if not voices:
        return [["-", "暂无音色", "-"]]
    rows = []
    for v in voices:
        preview = v["ref_text"][:40] + ("..." if len(v["ref_text"]) > 40 else "")
        rows.append([v["id"], v["name"], preview])
    return rows


def _history_table_rows() -> list[list[str]]:
    records = task_mgr.list_history()
    if not records:
        return []
    rows = []
    for r in records:
        created = r.get("created_at", "")[:16].replace("T", " ")
        total = r.get("total_lines", 0)
        success = r.get("success_lines", 0)
        rows.append([
            r.get("id", ""),
            created,
            r.get("voice_name", "-"),
            r.get("text_preview", ""),
            f"{success}/{total}",
        ])
    return rows


# ============================================================
# Tab 1 回调：音色管理
# ============================================================


def on_audio_uploaded(ref_wav_path: str | None) -> tuple:
    """上传音频后自动处理：ASR 识别 + 超长自动截取"""
    if not ref_wav_path:
        return (
            "",  # ref_text
            gr.update(value="", visible=False),  # extract_info
            gr.update(value=None, visible=False),  # extracted_audio
            gr.update(visible=False),  # use_extracted
            None,  # extracted_path_state
            None,  # saved_path_state
            "",  # voice_msg
        )

    try:
        # 立即把上传文件保存到持久目录，避免 Gradio 清理临时文件
        import shutil, uuid
        from config import REFS_RAW_DIR
        REFS_RAW_DIR.mkdir(parents=True, exist_ok=True)
        src = Path(ref_wav_path)
        saved_name = f"{uuid.uuid4().hex[:8]}_{src.name}"
        saved_path = str(REFS_RAW_DIR / saved_name)
        shutil.copy2(ref_wav_path, saved_path)

        duration = audio_processor.get_audio_duration(saved_path)

        if duration > MAX_REF_DURATION_SECS:
            ext_path, start, end = audio_processor.extract_best_segment(saved_path)
            seg_dur = end - start
            asr_text = audio_processor.transcribe_audio(ext_path)
            info_html = (
                f'<div style="padding:8px;background:#fff3cd;border-radius:4px;">'
                f"原始音频 {duration:.1f}s，已自动提取 {start:.1f}s-{end:.1f}s 段 "
                f"({seg_dur:.1f}s)。ASR 识别文本已填入，请检查修改。"
                f"</div>"
            )
            return (
                asr_text,
                gr.update(value=info_html, visible=True),
                gr.update(value=ext_path, visible=True),
                gr.update(visible=True, value=True),
                ext_path,  # extracted_path_state
                saved_path,  # saved_path_state
                "音频已处理",
            )

        # 短音频：仅 ASR
        asr_text = audio_processor.transcribe_audio(saved_path)
        info_html = (
            f'<div style="padding:8px;background:#d4edda;border-radius:4px;">'
            f"音频时长 {duration:.1f}s，ASR 识别文本已填入，请检查修改。"
            f"</div>"
        )
        return (
            asr_text,
            gr.update(value=info_html, visible=True),
            gr.update(value=None, visible=False),
            gr.update(visible=False),
            None,  # extracted_path_state
            saved_path,  # saved_path_state
            "音频已识别",
        )
    except Exception as e:
        err_html = (
            f'<div style="padding:8px;background:#f8d7da;border-radius:4px;">'
            f"处理失败: {e}</div>"
        )
        return (
            "",
            gr.update(value=err_html, visible=True),
            gr.update(value=None, visible=False),
            gr.update(visible=False),
            None,
            None,
            f"处理失败: {e}",
        )


def on_add_voice(
    name: str,
    ref_text: str,
    ref_wav_path: str | None,
    use_extracted: bool,
    extracted_path: str | None,
    saved_path: str | None,
) -> tuple:
    if not name or not ref_text:
        return (
            _voice_table_rows(), "请填写音色名称和参考文本",
            "", "", None,
            gr.update(visible=False), gr.update(value="", visible=False), gr.update(value=None, visible=False), None, None,
        )
    # 优先用持久化的 saved_path，fallback 到 ref_wav_path
    source_path = saved_path or ref_wav_path
    if not source_path:
        return (
            _voice_table_rows(), "请上传参考音频",
            "", "", None,
            gr.update(visible=False), gr.update(value="", visible=False), gr.update(value=None, visible=False), None, None,
        )

    actual_path = extracted_path if (use_extracted and extracted_path) else source_path

    try:
        voice_mgr.add_voice(name, actual_path, ref_text)
        return (
            _voice_table_rows(),
            f"音色「{name}」添加成功",
            "",   # clear name
            "",   # clear ref_text
            None, # clear ref_wav
            gr.update(visible=False),                  # use_extracted
            gr.update(value="", visible=False),        # extract_info
            gr.update(value=None, visible=False),      # extracted_audio
            None,  # clear extracted_path_state
            None,  # clear saved_path_state
        )
    except Exception as e:
        return (
            _voice_table_rows(),
            f"添加失败: {e}",
            name,
            ref_text,
            ref_wav_path,
            gr.update(visible=use_extracted),
            gr.update(value="", visible=True),
            gr.update(value=extracted_path, visible=True),
            extracted_path,
            saved_path,
        )


def on_voice_selected(evt: gr.SelectData, table_data: list) -> tuple:
    """点击音色表格行 → 填充编辑区 + 记录选中 ID"""
    vid = None

    # 方式1: evt.row_value (Gradio 5 部分版本支持)
    if evt.row_value:
        vid = evt.row_value[0]
    # 方式2: evt.value
    elif evt.value and evt.value != "-":
        vid = evt.value
    # 方式3: 通过 index 从 table_data 取
    elif evt.index is not None and table_data:
        rows = _table_data(table_data)
        idx = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
        if 0 <= idx < len(rows):
            vid = rows[idx][0]

    if not vid or vid == "-":
        return "", "", None, '<div style="padding:10px;color:#888;">请先选择音色</div>'

    voice = voice_mgr.get_voice(vid)
    if voice:
        return voice["name"], voice["ref_text"], vid, _wav_to_html(voice["ref_wav"])
    return "", "", None, '<div style="padding:10px;color:#888;">未找到该音色</div>'


def on_update_voice(edit_name: str, edit_ref_text: str, sel_id: str | None) -> tuple:
    if not sel_id:
        return _voice_table_rows(), "请先在表格中选择一个音色", edit_name, edit_ref_text, '<div style="padding:10px;color:#888;">请先选择音色</div>'
    name_val = edit_name.strip() or None
    text_val = edit_ref_text.strip() or None
    if not name_val and not text_val:
        return _voice_table_rows(), "请至少填写一个要修改的字段", edit_name, edit_ref_text, '<div style="padding:10px;color:#888;">请先选择音色</div>'
    result = voice_mgr.update_voice(sel_id, name=name_val, ref_text=text_val)
    if result:
        return _voice_table_rows(), f"音色「{result['name']}」已更新", "", "", '<div style="padding:10px;color:#888;">点击音色表格预览音频</div>'
    return _voice_table_rows(), "未找到该音色", edit_name, edit_ref_text, '<div style="padding:10px;color:#888;">未找到该音色</div>'


def on_delete_voice(sel_id: str | None) -> tuple:
    if not sel_id:
        return _voice_table_rows(), "请先选择一个音色", "", "", '<div style="padding:10px;color:#888;">请先选择音色</div>'
    name = voice_mgr.get_name_map().get(sel_id, sel_id)
    voice_mgr.delete_voice(sel_id)
    return _voice_table_rows(), f"音色「{name}」已删除", "", "", '<div style="padding:10px;color:#888;">点击音色表格预览音频</div>'


# ============================================================
# Tab 2 回调：语音生成
# ============================================================


def on_voice_dropdown_change(voice_id: str | None) -> str:
    if not voice_id:
        return '<div style="padding:10px;color:#888;">请先选择音色</div>'
    voice = voice_mgr.get_voice(voice_id)
    if voice:
        return _wav_to_html(voice["ref_wav"])
    return '<div style="padding:10px;color:#888;">音色不存在</div>'


def on_refresh_voices() -> gr.update:
    return gr.update(choices=voice_mgr.get_choices())


def on_generate(voice_id: str | None, text: str, silence_secs: float) -> tuple:
    if not voice_id:
        return '<div style="padding:10px;color:#888;">请先选择音色</div>', "请先选择音色", _history_table_rows()
    if not text or not text.strip():
        return '<div style="padding:10px;color:#888;">请输入文本</div>', "请输入文本", _history_table_rows()

    voice = voice_mgr.get_voice(voice_id)
    if not voice:
        return '<div style="padding:10px;color:#888;">音色不存在</div>', "音色不存在", _history_table_rows()

    merged_path, status = task_mgr.generate(
        voice_id=voice_id,
        voice_name=voice["name"],
        ref_wav=voice["ref_wav"],
        ref_text=voice["ref_text"],
        text=text,
        silence_secs=silence_secs,
    )
    return _wav_to_html(merged_path), status, _history_table_rows()


# ============================================================
# Tab 3 回调：历史记录
# ============================================================


def on_play_history(evt: gr.SelectData, table_data: list) -> str:
    if evt.index is None:
        return '<div style="padding:10px;color:#888;">请点击一条记录</div>'
    idx = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
    records = task_mgr.list_history()
    if 0 <= idx < len(records):
        return _wav_to_html(records[idx].get("merged_path", ""))
    return '<div style="padding:10px;color:#888;">未找到音频</div>'


def on_refresh_history() -> list:
    return _history_table_rows()


def on_history_select_combined(evt: gr.SelectData) -> tuple:
    if evt.index is None:
        return None, gr.update()
    
    idx = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
    records = task_mgr.list_history()
    
    if 0 <= idx < len(records):
        record = records[idx]
        rec_id = record.get("id")
        audio_html = _wav_to_html(record.get("merged_path"))
        print(f"[DEBUG] 选中历史记录: ID={rec_id}, Index={idx}")
        return rec_id, audio_html
    
    return None, '<div style="padding:10px;color:#888;">未找到音频</div>'


def on_delete_history(record_id: str) -> tuple:
    print(f"[DEBUG] 触发删除请求: ID={record_id}")
    if not record_id:
        return _history_table_rows(), '<div style="padding:10px;color:red;">未选中记录</div>', None
    
    success = task_mgr.delete_history(record_id)
    if success:
        return _history_table_rows(), '<div style="padding:10px;color:green;">已删除记录及文件</div>', None
    
    return _history_table_rows(), f'<div style="padding:10px;color:red;">删除失败 (ID: {record_id})</div>', record_id


# ============================================================
# 构建 UI
# ============================================================


def build_ui():
    with gr.Blocks(
        title="Voice WebUI",
        css=CSS,
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"),
    ) as demo:

        gr.Markdown("# Voice WebUI\n基于 CosyVoice 的本地语音克隆合成工具")

        with gr.Tabs():
            # ===== Tab 1: 音色管理 =====
            with gr.Tab("音色管理"):
                gr.Markdown("管理语音克隆音色。上传参考音频（8-15秒干声）并填写对应文本。")

                voice_table = gr.Dataframe(
                    headers=["ID", "名称", "参考文本"],
                    label="已注册音色",
                    interactive=False,
                    value=_voice_table_rows(),
                )

                gr.Markdown("---")
                gr.Markdown("**添加新音色**")
                with gr.Row():
                    new_name = gr.Textbox(label="音色名称", placeholder="如：温柔女声", scale=1)
                    new_ref_text = gr.Textbox(label="参考文本", placeholder="参考音频对应文字", scale=2)
                new_ref_wav = gr.Audio(label="参考音频", type="filepath", sources=["upload"])
                extract_info = gr.HTML("", visible=False)
                extracted_audio = gr.Audio(label="截取片段试听", type="filepath", interactive=False, visible=False)
                use_extracted = gr.Checkbox(label="使用截取片段", value=True, visible=False)
                extracted_path_state = gr.State(None)
                saved_path_state = gr.State(None)
                add_btn = gr.Button("添加音色", variant="primary")
                voice_msg = gr.Textbox(label="状态", interactive=False)

                gr.Markdown("---")
                gr.Markdown("**编辑 / 删除选中音色**")
                with gr.Row():
                    edit_name = gr.Textbox(label="修改名称", scale=1)
                    edit_ref_text = gr.Textbox(label="修改参考文本", scale=2)
                voice_preview_sel = gr.HTML(
                    value='<div style="padding:10px;color:#888;">点击音色表格预览音频</div>',
                )

                sel_voice_id = gr.State(None)

                with gr.Row():
                    update_btn = gr.Button("更新", variant="secondary")
                    delete_btn = gr.Button("删除", variant="stop")

            # ===== Tab 2: 语音生成 =====
            with gr.Tab("语音生成"):
                gr.Markdown("选择音色 → 粘贴文本 → 按段落拆分生成 → 自动合并为完整音频")

                with gr.Row():
                    with gr.Column(scale=1):
                        _init_choices = voice_mgr.get_choices()
                        _init_voice_id = _init_choices[0][1] if _init_choices else None
                        _init_preview = on_voice_dropdown_change(_init_voice_id) if _init_voice_id else '<div style="padding:10px;color:#888;">请先选择音色</div>'
                        voice_dd = gr.Dropdown(
                            label="选择音色",
                            choices=_init_choices,
                            value=_init_voice_id,
                            interactive=True,
                        )
                        voice_preview = gr.HTML(
                            value=_init_preview,
                        )
                        silence_slider = gr.Slider(
                            minimum=0.0, maximum=1.0, value=0.35,
                            step=0.05, label="段间静音（秒）",
                        )
                        with gr.Row():
                            refresh_btn = gr.Button("刷新音色列表")

                    with gr.Column(scale=2):
                        gen_text = gr.Textbox(
                            label="待合成文本",
                            placeholder="在此粘贴文本，按换行自动拆分段落...",
                            lines=15,
                        )
                        gen_btn = gr.Button("开始生成", variant="primary")

                gen_status = gr.Textbox(label="状态", interactive=False)
                result_audio = gr.HTML(
                    value='<div style="padding:10px;color:#888;">等待生成...</div>',
                )

            # ===== Tab 3: 历史记录 =====
            with gr.Tab("历史记录"):
                gr.Markdown("点击某一行可播放对应音频")

                history_table = gr.Dataframe(
                    headers=["ID", "时间", "音色", "文本预览", "段数"],
                    label="生成历史",
                    interactive=False,
                    value=_history_table_rows(),
                )
                
                sel_history_id = gr.State(None)
                
                with gr.Row():
                    refresh_hist_btn = gr.Button("刷新记录")
                    delete_hist_btn = gr.Button("删除选中记录", variant="stop")
                
                history_audio = gr.HTML(
                    value='<div style="padding:10px;color:#888;">点击记录播放</div>',
                )

        # ===== 事件绑定 =====
        # Tab 1
        new_ref_wav.change(
            on_audio_uploaded,
            [new_ref_wav],
            [new_ref_text, extract_info, extracted_audio, use_extracted, extracted_path_state, saved_path_state, voice_msg],
        )
        add_btn.click(
            on_add_voice,
            [new_name, new_ref_text, new_ref_wav, use_extracted, extracted_path_state, saved_path_state],
            [voice_table, voice_msg, new_name, new_ref_text, new_ref_wav, use_extracted, extract_info, extracted_audio, extracted_path_state, saved_path_state],
        )
        voice_table.select(on_voice_selected, [voice_table], [edit_name, edit_ref_text, sel_voice_id, voice_preview_sel])
        update_btn.click(on_update_voice, [edit_name, edit_ref_text, sel_voice_id], [voice_table, voice_msg, edit_name, edit_ref_text, voice_preview_sel])
        delete_btn.click(on_delete_voice, [sel_voice_id], [voice_table, voice_msg, edit_name, edit_ref_text, voice_preview_sel])

        # Tab 2
        gen_btn.click(on_generate, [voice_dd, gen_text, silence_slider], [result_audio, gen_status, history_table])
        refresh_btn.click(on_refresh_voices, outputs=[voice_dd])
        voice_dd.change(on_voice_dropdown_change, [voice_dd], [voice_preview])

        # Tab 3
        refresh_hist_btn.click(on_refresh_history, outputs=[history_table])
        history_table.select(on_history_select_combined, None, [sel_history_id, history_audio])
        delete_hist_btn.click(on_delete_history, [sel_history_id], [history_table, history_audio, sel_history_id])

        # 页面加载时刷新
        demo.load(on_refresh_history, outputs=[history_table])

    return demo


# ============================================================
# 启动
# ============================================================


def main():
    print("=" * 50)
    print("ccwebui 启动中...")
    print("正在加载 CosyVoice 模型...")
    msg = task_mgr.load_model()
    print(msg)

    if PRELOAD_ASR_ON_START:
        print("正在加载 SenseVoice ASR 模型...")
        try:
            audio_processor.preload_asr_model()
            print("ASR 模型已加载")
        except Exception as e:
            print(f"ASR 模型加载失败: {e}")
            print("语音识别功能不可用，其他功能正常")
    else:
        print("ASR 模型将在上传参考音频时按需加载")

    demo = build_ui()
    demo.queue(max_size=1)
    demo.launch(
        server_name=SERVER_NAME,
        server_port=SERVER_PORT,
        inbrowser=True,
        allowed_paths=[str(REFS_DIR), str(OUTPUTS_DIR)],
    )


if __name__ == "__main__":
    main()
