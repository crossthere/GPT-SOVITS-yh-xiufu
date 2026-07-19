# GPT-SOVITS-yh-xiufu
彻底解决TTS 吞字问题。并新增字幕。时长控制。原理是通过TTs生成的字幕然后判断字幕时长 小于0.几 就确定吞字了。然后重新生成20次内必定生成成功，然后补上。

## 使用说明

1. 本工具依赖 GPT-SoVITS API，请先在 GPT-SoVITS 项目中自行开启 API 接口。默认接口地址为 `http://127.0.0.1:9880`。
2. 将 `ffmpeg.exe` 放到本项目根目录。程序会使用它剪切、拼接并修补音频。
3. 安装 Python 依赖：

   ```bash
   pip install -r requirements.txt
   ```

4. 启动界面：

   ```bash
   python MP3_shenc/mp3test.py
   ```

5. 运行前请确认代码中所配置的 GPT、SoVITS 模型及参考音频路径均可被 GPT-SoVITS API 正确访问。

语音合成交流：q 2578017198
