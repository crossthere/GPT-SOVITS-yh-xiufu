import tkinter as tk
from tkinter import scrolledtext, messagebox
import requests
import os
import re
import shutil
import subprocess
import tempfile
import wave
from datetime import datetime
import threading

try:
    from MP3_shenc.mp3_api_creat import (
        API_BASE,
        build_tts_payload as build_api_tts_payload,
        fetch_tts_segments,
        sentence_newline_text,
        synthesize_tts_to_file,
    )
except ModuleNotFoundError:
    from mp3_api_creat import (
        API_BASE,
        build_tts_payload as build_api_tts_payload,
        fetch_tts_segments,
        sentence_newline_text,
        synthesize_tts_to_file,
    )

FIRST_SUBTITLE_START_OFFSET = 0.1

# 音频人物配置
VOICE_CONFIGS = {
    "文彤": {
        "gpt_weights": "GPT_weights_v2Pro/dg_wentong-e15.ckpt",
        "sovits_weights": "SoVITS_weights_v2Pro/dg_wentong_e8_s408.pth",
        "ref_audio": "yinpin_cankao/dou_wentong老一辈传下的硬道理，我给你换成更好执行的顺手做法。.wav",
        "ref_text": "老一辈传下的硬道理，我给你换成更好执行的顺手做法。"
    },
    "逗姥爷": {
        "gpt_weights": "GPT_weights_v2Pro/dou_laoye3-e15.ckpt",
        "sovits_weights": "SoVITS_weights_v2Pro/dou_laoye3_e8_s896.pth",
        "ref_audio": "yinpin_cankao/dou_laoye老一辈常说，命再硬，也硬不过坏习惯.wav",
        "ref_text": "老一辈常说，命再硬，也硬不过坏习惯"
    },
    "逗浩泽": {
        "gpt_weights": "GPT_weights_v2Pro/dg_douhaoze-e10.ckpt",
        "sovits_weights": "SoVITS_weights_v2Pro/dg_douhaoze_e8_s568.pth",
        "ref_audio": "yinpin_cankao/dou_haoze_看着没事，其实底子在往下漏。有人闯过，路宽身稳。.wav",
        "ref_text": "看着没事，其实底子在往下漏。有人闯过，路宽身稳。"
    }
}


class TTSTestGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("语音生成测试")
        self.root.geometry("450x500")
        
        # 初始化标志和当前配音员
        self.is_initialized = False
        self.voice_options = list(VOICE_CONFIGS.keys())
        self.current_voice = self.voice_options[0]
        
        # 标题
        title_label = tk.Label(root, text="语音生成测试", font=("微软雅黑", 16, "bold"))
        title_label.pack(pady=10)

        contact_label = tk.Label(root, text="语音合成交流：q 2578017198", font=("微软雅黑", 10), fg="#1976D2")
        contact_label.pack(pady=(0, 5))
        
        # 配音员选择
        voice_frame = tk.Frame(root)
        voice_frame.pack(pady=5)
        tk.Label(voice_frame, text="配音员:", font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
        
        self.voice_var = tk.StringVar(value=self.current_voice)
        for voice in self.voice_options:
            tk.Radiobutton(voice_frame, text=voice, variable=self.voice_var, 
                          value=voice, font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=5)
        
        tk.Button(voice_frame, text="更新模型", command=self.update_model,
                 bg="#2196F3", fg="white", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=10)
        
        # 输入文本区域
        tk.Label(root, text="输入文本:", font=("微软雅黑", 10)).pack(anchor="w", padx=20)
        self.text_input = scrolledtext.ScrolledText(root, height=8, width=55, font=("微软雅黑", 10))
        self.text_input.pack(padx=20, pady=5)
        
        # 生成选项
        options_frame = tk.Frame(root)
        options_frame.pack(pady=5)

        self.generate_srt_var = tk.BooleanVar(value=True)
        srt_checkbox = tk.Checkbutton(options_frame, text="同时生成 SRT 字幕文件", 
                                      variable=self.generate_srt_var,
                                      font=("微软雅黑", 9))
        srt_checkbox.pack(side=tk.LEFT, padx=5)

        self.sentence_split_optimize_var = tk.BooleanVar(value=False)
        sentence_split_checkbox = tk.Checkbutton(options_frame, text="按句分割优化",
                                                 variable=self.sentence_split_optimize_var,
                                                 font=("微软雅黑", 9))
        sentence_split_checkbox.pack(side=tk.LEFT, padx=5)

        self.auto_compensate_var = tk.BooleanVar(value=True)
        compensate_checkbox = tk.Checkbutton(options_frame, text="自动补偿吞段",
                                             variable=self.auto_compensate_var,
                                             font=("微软雅黑", 9))
        compensate_checkbox.pack(side=tk.LEFT, padx=5)
        
        # 测试按钮
        self.test_btn = tk.Button(root, text="生成语音", command=self.generate_audio, 
                                   bg="#4CAF50", fg="white", font=("微软雅黑", 12, "bold"),
                                   padx=20, pady=10, cursor="hand2")
        self.test_btn.pack(pady=10)
        
        # 状态显示
        self.status_label = tk.Label(root, text="状态: 就绪", font=("微软雅黑", 9), fg="gray")
        self.status_label.pack(pady=5)
        
        # 启动时初始化模型
        self.init_models(self.current_voice)
    
    def update_status(self, message, color="gray"):
        """更新状态显示"""
        self.status_label.config(text=f"状态: {message}", fg=color)
        self.root.update()
    
    def update_model(self):
        """更新模型到选中的配音员"""
        selected_voice = self.voice_var.get()
        if selected_voice != self.current_voice:
            self.current_voice = selected_voice
            self.init_models(selected_voice)
        else:
            messagebox.showinfo("提示", f"当前已是 {selected_voice} 模型")
    
    def format_srt_time(self, seconds):
        """将秒数转换为 SRT 时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def split_subtitle_by_length(self, text, max_length=15):
        """
        按长度和标点符号智能分割字幕
        - 尽量不超过 max_length 个字
        - 保持语义完整性
        - **只在标点符号处分割**
        - 如果15字内没有标点，允许超过以保持完整性
        """
        # 删除末尾的句号和逗号（保留感叹号和问号）
        text = text.rstrip('.').rstrip(',').rstrip('。').rstrip('，')
        
        if len(text) <= max_length:
            return [text]
        
        # 标点符号列表（包含中文和英文标点）
        punctuations = ['。', '！', '？', '；', '，', '、', '.', ',', '!', '?']
        
        result = []
        current = ""
        min_length = 10  # 最小长度阈值
        
        for char in text:
            current += char
            
            # **只在遇到标点符号时才分割**
            if char in punctuations:
                # 如果当前段长度 >= 10字，就分割
                # （这样避免太短的分段，同时保证在标点处分割）
                if len(current) >= min_length:
                    # 删除末尾的句号、逗号、分号（保留感叹号和问号）
                    cleaned = current.strip().rstrip('.,，。；;')
                    if cleaned:  # 确保不是空字符串
                        result.append(cleaned)
                    current = ""
                # 如果太短（<10字），继续累积
        
        # 处理剩余内容（没有标点符号结尾的部分）
        if current.strip():
            # 如果剩余内容很短，且合并后不会太长，尝试合并到上一段
            if result and len(current) <= 8 and len(result[-1]) + len(current) <= 18:
                result[-1] = (result[-1] + current).rstrip('.,，。；;')
            else:
                # 删除末尾的句号、逗号、分号（保留感叹号和问号）
                cleaned = current.strip().rstrip('.,，。；;')
                if cleaned:  # 确保不是空字符串
                    result.append(cleaned)
        
        return [s for s in result if s]  # 过滤空字符串
    
    def split_time_by_text_ratio(self, text, start_time, end_time):
        """
        根据文字占比分配时间
        返回: [(sub_text, sub_start, sub_end), ...]
        """
        sub_texts = self.split_subtitle_by_length(text)
        if len(sub_texts) == 1:
            return [(text, start_time, end_time)]
        
        total_duration = end_time - start_time
        total_chars = sum(len(t) for t in sub_texts)
        
        result = []
        current_time = start_time
        
        for sub_text in sub_texts:
            # 按字符数占比分配时间
            char_ratio = len(sub_text) / total_chars
            sub_duration = total_duration * char_ratio
            sub_end = current_time + sub_duration
            
            result.append((sub_text, current_time, sub_end))
            current_time = sub_end
        
        return result

    def extract_book_title_contents(self, text):
        """记录原文中《》里的内容，用于恢复接口元数据里丢失的书名号。"""
        titles = []
        seen = set()
        for match in re.findall(r'《([^《》]+)》', text):
            title = match.strip()
            if title and title not in seen:
                titles.append(title)
                seen.add(title)
        return titles

    def restore_book_title_marks(self, text, book_title_contents):
        """把已记录的书名号内容补回到字幕文本里。"""
        if not book_title_contents:
            return text

        for title in sorted(book_title_contents, key=len, reverse=True):
            title_pattern = re.escape(title)
            text = re.sub(rf'(?<!《)({title_pattern})(?!》)', r'《\1》', text)
        return text

    def count_content_chars(self, text):
        """统计正文字符数，忽略空白和常见标点。"""
        punctuations = set("，。！？；：、,.!?;:（）()《》<>“”\"'‘’【】[]—-…")
        return sum(1 for char in text if not char.isspace() and char not in punctuations)

    def calculate_subtitle_quality(self, subtitle_segments, min_seconds_per_char=0.15):
        """统计疑似吞段：最终 SRT 中时长低于“每字最低时长”的字幕条。"""
        total = len(subtitle_segments)
        swallowed_indices = []

        for index, (text, start_time, end_time) in enumerate(subtitle_segments, 1):
            content_chars = self.count_content_chars(text)
            duration = end_time - start_time
            min_duration = content_chars * min_seconds_per_char
            if content_chars > 0 and duration < min_duration:
                swallowed_indices.append(index)

        swallowed_count = len(swallowed_indices)
        complete_rate = 100.0 if total == 0 else (total - swallowed_count) * 100 / total

        return {
            "total": total,
            "swallowed_count": swallowed_count,
            "swallowed_indices": swallowed_indices,
            "complete_rate": complete_rate,
            "min_seconds_per_char": min_seconds_per_char
        }

    def build_optimized_segments(self, segments):
        """把接口返回分段转换成最终 SRT 使用的字幕条。"""
        segments = sorted(segments, key=lambda x: x['start_time'])
        optimized_segments = []

        for seg in segments:
            text = seg['text']
            start_time = seg['start_time']
            end_time = seg['end_time']
            sub_segments = self.split_time_by_text_ratio(text, start_time, end_time)
            optimized_segments.extend(sub_segments)

        return optimized_segments

    def write_srt_segments(self, subtitle_segments, srt_path, book_title_contents=None):
        """写入 SRT 文件。"""
        with open(srt_path, 'w', encoding='utf-8') as f:
            for i, (text, start_time, end_time) in enumerate(subtitle_segments, 1):
                if i == 1 and abs(start_time) < 0.001 and end_time > FIRST_SUBTITLE_START_OFFSET:
                    start_time = FIRST_SUBTITLE_START_OFFSET
                text = self.restore_book_title_marks(text, book_title_contents)
                f.write(f"{i}\n")
                f.write(f"{self.format_srt_time(start_time)} --> {self.format_srt_time(end_time)}\n")
                f.write(f"{text}\n\n")
    
    def generate_srt_file(self, segments, srt_path, book_title_contents=None):
        """生成优化后的 SRT 字幕文件"""
        optimized_segments = self.build_optimized_segments(segments)
        self.write_srt_segments(optimized_segments, srt_path, book_title_contents)
        quality = self.calculate_subtitle_quality(optimized_segments)
        quality["subtitle_segments"] = optimized_segments
        return quality

    def get_ffmpeg_path(self):
        """获取项目根目录下的 ffmpeg.exe。"""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        ffmpeg_path = os.path.join(project_root, "ffmpeg.exe")
        if not os.path.exists(ffmpeg_path):
            raise FileNotFoundError(f"未找到 ffmpeg.exe: {ffmpeg_path}")
        return ffmpeg_path

    def get_wav_duration(self, wav_path):
        """读取 WAV 时长。"""
        with wave.open(wav_path, "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return frames / float(rate)

    def build_tts_payload(self, text, voice_config, split_method, sentence_newline=False):
        """构建 TTS 请求参数。"""
        return build_api_tts_payload(
            text,
            voice_config,
            split_method,
            sentence_newline=sentence_newline,
        )

    def synthesize_to_file(self, text, voice_config, split_method, output_path, timeout=600):
        """用指定切分方式合成音频，并返回对应字幕质量。"""
        synthesize_tts_to_file(
            text,
            voice_config,
            split_method,
            output_path,
            timeout=timeout,
            sentence_newline=False,
            error_label=f"{split_method} 补偿合成失败",
        )

        segments = fetch_tts_segments(timeout=10, error_label=f"{split_method} 获取补偿元数据失败")
        optimized_segments = self.build_optimized_segments(segments) if segments else []
        quality = self.calculate_subtitle_quality(optimized_segments)
        quality["subtitle_segments"] = optimized_segments
        quality["duration"] = self.get_wav_duration(output_path)
        return quality

    def synthesize_compensation(self, index, text, voice_config, temp_dir, max_attempts=20):
        """用 cut1 多次尝试合成单段补偿音频。"""
        safe_index = f"{index:04d}"
        split_method = "cut1"
        for attempt in range(1, max_attempts + 1):
            output_path = os.path.join(temp_dir, f"comp_{safe_index}_{split_method}_{attempt:02d}.wav")
            quality = self.synthesize_to_file(text, voice_config, split_method, output_path)
            if quality["swallowed_count"] == 0:
                print(
                    f"补偿成功: 第 {index} 段 cut1 第 {attempt}/{max_attempts} 次, "
                    f"时长 {quality['duration']:.3f}s, 文本: {text}",
                    flush=True
                )
                return {
                    "index": index,
                    "method": split_method,
                    "attempt": attempt,
                    "path": output_path,
                    "duration": quality["duration"]
                }

            print(
                f"补偿失败: 第 {index} 段 cut1 第 {attempt}/{max_attempts} 次仍吞段 "
                f"{quality['swallowed_count']} 段, 时长 {quality['duration']:.3f}s, 文本: {text}",
                flush=True
            )

        return None

    def run_ffmpeg(self, args):
        """运行 ffmpeg，失败时抛出 stderr。"""
        command = [self.get_ffmpeg_path()] + args
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        if result.returncode != 0:
            raise Exception(result.stderr.strip())

    def export_audio_slice(self, source_path, start_time, end_time, output_path):
        """从原音频导出一个片段。"""
        duration = end_time - start_time
        if duration <= 0.01:
            return False

        self.run_ffmpeg([
            "-y",
            "-ss", f"{start_time:.6f}",
            "-t", f"{duration:.6f}",
            "-i", source_path,
            "-c:a", "pcm_s16le",
            output_path
        ])
        return True

    def concat_audio_parts(self, part_paths, output_path, temp_dir):
        """把多个 WAV 片段拼接成一个 WAV。"""
        concat_list = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for part_path in part_paths:
                escaped_path = part_path.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        self.run_ffmpeg([
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
            "-c:a", "pcm_s16le",
            output_path
        ])

    def compensate_audio_and_srt(self, original_wav, subtitle_segments, replacements, output_wav, output_srt, temp_dir, book_title_contents=None):
        """用补偿音频替换失败段，并重算 SRT 时间轴。"""
        replacement_map = {item["index"]: item for item in replacements}
        part_paths = []
        current_original_time = 0.0

        for index, (_, start_time, end_time) in enumerate(subtitle_segments, 1):
            replacement = replacement_map.get(index)
            if not replacement:
                continue

            slice_path = os.path.join(temp_dir, f"slice_before_{index:04d}.wav")
            if self.export_audio_slice(original_wav, current_original_time, start_time, slice_path):
                part_paths.append(slice_path)

            part_paths.append(replacement["path"])
            current_original_time = end_time

        original_duration = self.get_wav_duration(original_wav)
        tail_path = os.path.join(temp_dir, "slice_tail.wav")
        if self.export_audio_slice(original_wav, current_original_time, original_duration, tail_path):
            part_paths.append(tail_path)

        if not part_paths:
            return None

        self.concat_audio_parts(part_paths, output_wav, temp_dir)

        new_segments = []
        current_shift = 0.0
        for index, (text, start_time, end_time) in enumerate(subtitle_segments, 1):
            replacement = replacement_map.get(index)
            if replacement:
                new_start = start_time + current_shift
                new_end = new_start + replacement["duration"]
                current_shift += replacement["duration"] - (end_time - start_time)
            else:
                new_start = start_time + current_shift
                new_end = end_time + current_shift

            new_segments.append((text, new_start, new_end))

        self.write_srt_segments(new_segments, output_srt, book_title_contents)
        quality = self.calculate_subtitle_quality(new_segments)
        quality["subtitle_segments"] = new_segments
        return quality

    def compensate_failed_segments(self, output_file, subtitle_segments, quality, voice_config, book_title_contents=None, max_attempts=20):
        """对检测失败的字幕段执行自动补偿。"""
        failed_indices = quality.get("swallowed_indices", [])
        if not failed_indices:
            return None

        temp_dir = tempfile.mkdtemp(prefix="tts_comp_", dir=os.path.dirname(output_file))
        try:
            replacements = []
            for index in failed_indices:
                text, start_time, end_time = subtitle_segments[index - 1]
                self.update_status(f"正在补偿第 {index} 段...", "orange")
                replacement = self.synthesize_compensation(index, text, voice_config, temp_dir, max_attempts)
                if replacement:
                    replacement["original_duration"] = end_time - start_time
                    replacements.append(replacement)
                else:
                    print(f"补偿放弃: 第 {index} 段 cut1 连续 {max_attempts} 次均未通过, 文本: {text}", flush=True)

            if not replacements:
                return {
                    "replaced_count": 0,
                    "quality": quality,
                    "output_wav": None,
                    "output_srt": None
                }

            output_wav = output_file.replace(".wav", "_compensated.wav")
            output_srt = output_file.replace(".wav", "_compensated.srt")
            compensated_quality = self.compensate_audio_and_srt(
                output_file,
                subtitle_segments,
                replacements,
                output_wav,
                output_srt,
                temp_dir,
                book_title_contents
            )

            return {
                "replaced_count": len(replacements),
                "quality": compensated_quality,
                "output_wav": output_wav,
                "output_srt": output_srt
            }
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def replace_original_with_compensated(self, original_wav, original_srt, compensated_wav, compensated_srt):
        """用补偿后的成品覆盖原始输出，只保留一套最终文件。"""
        os.replace(compensated_wav, original_wav)
        os.replace(compensated_srt, original_srt)
    
    def remove_blank_lines(self, text):
        """删除所有空白行，保留非空行之间的正常换行。"""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    
    def preprocess_text(self, text):
        """
        预处理文本：清理空行；可选按句分割优化。
        """
        text = self.remove_blank_lines(text)

        if not self.sentence_split_optimize_var.get():
            return text

        # 在这些标点后面添加句号，兼容只按“。”断句的切分方式。
        text = re.sub(r'？(?!。)', '？。', text)
        text = re.sub(r'！(?!。)', '！。', text)
        text = re.sub(r'；(?!。)', '；。', text)
        text = re.sub(r'——(?!。)', '——。', text)
        text = re.sub(r'--(?!。)', '--。', text)
        return text
    
    def init_models(self, voice_name):
        """初始化模型权重"""
        def init_thread():
            try:
                self.update_status(f"正在初始化 {voice_name} 模型...", "orange")
                self.test_btn.config(state="disabled")
                
                # 获取配音员配置
                voice_config = VOICE_CONFIGS.get(voice_name)
                if not voice_config:
                    raise Exception(f"未找到配音员配置: {voice_name}")
                
                # 设置GPT权重
                response = requests.get(f"{API_BASE}/set_gpt_weights", 
                                       params={"weights_path": voice_config["gpt_weights"]}, 
                                       timeout=30)
                if response.status_code != 200:
                    raise Exception(f"设置GPT权重失败: {response.text}")
                
                # 设置SoVITS权重
                response = requests.get(f"{API_BASE}/set_sovits_weights", 
                                       params={"weights_path": voice_config["sovits_weights"]}, 
                                       timeout=30)
                if response.status_code != 200:
                    raise Exception(f"设置SoVITS权重失败: {response.text}")
                
                self.is_initialized = True
                self.current_voice = voice_name
                self.update_status(f"{voice_name} 模型就绪", "green")
                self.test_btn.config(state="normal")
                
            except Exception as e:
                self.update_status(f"初始化失败: {str(e)}", "red")
                messagebox.showerror("初始化错误", f"模型初始化失败:\n{str(e)}")
                self.test_btn.config(state="normal")
        
        threading.Thread(target=init_thread, daemon=True).start()
    
    def generate_audio(self):
        """生成语音"""
        text = self.text_input.get("1.0", tk.END).strip()
        
        if not text:
            messagebox.showwarning("警告", "请输入文本！")
            return
        
        if not self.is_initialized:
            messagebox.showwarning("警告", "模型尚未初始化完成，请稍候...")
            return
        
        # 预处理文本：添加句号
        processed_text = self.preprocess_text(text)
        book_title_contents = self.extract_book_title_contents(processed_text)
        tts_text = sentence_newline_text(processed_text)
        if not tts_text:
            messagebox.showwarning("警告", "请输入有效文本！")
            return
        
        if tts_text != text:
            self.text_input.delete("1.0", tk.END)
            self.text_input.insert("1.0", tts_text)
            self.root.update()
        
        def generate_thread():
            try:
                self.update_status("正在生成语音...", "orange")
                self.test_btn.config(state="disabled")
                
                # 获取当前配音员配置
                voice_config = VOICE_CONFIGS.get(self.current_voice)
                if not voice_config:
                    raise Exception(f"未找到配音员配置: {self.current_voice}")
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(os.path.dirname(__file__), f"output_{timestamp}.wav")
                synthesize_tts_to_file(
                    tts_text,
                    voice_config,
                    "cut1",
                    output_file,
                    timeout=600,
                    sentence_newline=False,
                    error_label="API返回错误",
                )

                result_message = f"语音已生成:\n{os.path.basename(output_file)}"
                    
                if self.generate_srt_var.get():
                    try:
                        self.update_status("正在生成字幕...", "orange")
                        segments = fetch_tts_segments(timeout=10, error_label="获取元数据失败")
                            
                        if segments:
                            srt_file = output_file.replace(".wav", ".srt")
                            quality = self.generate_srt_file(segments, srt_file, book_title_contents)
                            subtitle_segments = quality["subtitle_segments"]
                            result_message += f"\n字幕已生成:\n{os.path.basename(srt_file)}"
                            result_message += f"\n\n共 {len(segments)} 个分段"
                            result_message += f"\n吞段 {quality['swallowed_count']} 段"
                            result_message += f"\n完整率 {quality['complete_rate']:.2f}%"

                            if quality["swallowed_indices"]:
                                print(
                                    "吞字段号(每字<0.15s): "
                                    + ", ".join(map(str, quality["swallowed_indices"])),
                                    flush=True
                                )
                            else:
                                print("吞字段号(每字<0.15s): 无", flush=True)

                            if self.auto_compensate_var.get() and quality["swallowed_count"] > 0:
                                try:
                                    self.update_status("正在自动补偿吞段...", "orange")
                                    compensation = self.compensate_failed_segments(
                                        output_file,
                                        subtitle_segments,
                                        quality,
                                        voice_config,
                                        book_title_contents
                                    )
                                    if compensation and compensation["output_wav"]:
                                        comp_quality = compensation["quality"]
                                        self.replace_original_with_compensated(
                                            output_file,
                                            srt_file,
                                            compensation["output_wav"],
                                            compensation["output_srt"]
                                        )
                                        result_message += "\n\n已用补偿结果覆盖原始音频和字幕"
                                        result_message += f"\n已替换 {compensation['replaced_count']} 段"
                                        result_message += f"\n最终吞段 {comp_quality['swallowed_count']} 段"
                                        result_message += f"\n最终完整率 {comp_quality['complete_rate']:.2f}%"

                                        if comp_quality["swallowed_indices"]:
                                            print(
                                                "最终仍吞字段号(每字<0.15s): "
                                                + ", ".join(map(str, comp_quality["swallowed_indices"])),
                                                flush=True
                                            )
                                        else:
                                            print("最终仍吞字段号(每字<0.15s): 无", flush=True)
                                    elif compensation:
                                        result_message += "\n\n自动补偿未成功替换任何片段"
                                except Exception as compensate_error:
                                    result_message += f"\n\n⚠️ 自动补偿失败: {str(compensate_error)}"
                                    print(f"自动补偿失败: {str(compensate_error)}", flush=True)
                        else:
                            result_message += "\n\n⚠️ 未获取到分段信息"
                        
                    except Exception as srt_error:
                        result_message += f"\n\n⚠️ 字幕生成失败: {str(srt_error)}"
                    
                self.update_status(f"生成成功", "green")
                messagebox.showinfo("成功", result_message)
                
            except Exception as e:
                self.update_status(f"生成失败: {str(e)}", "red")
                messagebox.showerror("错误", f"语音生成失败:\n{str(e)}")
            
            finally:
                self.test_btn.config(state="normal")
        
        threading.Thread(target=generate_thread, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = TTSTestGUI(root)
    root.mainloop()
