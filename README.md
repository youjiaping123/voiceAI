# 语音AI聊天机器人

这是一个基于MQTT协议的语音AI聊天机器人系统，支持语音输入、AI对话以及语音合成输出功能。系统使用Azure语音服务进行语音识别和合成，通过Claude AI模型处理对话。

## 系统架构

该系统主要包含两个核心组件：

1. **语音AI聊天机器人服务端** (voice_ai_chatbot.py)
   - 订阅MQTT音频数据主题
   - 使用Azure Speech Services进行语音识别(STT)
   - 调用Claude AI进行对话处理
   - 使用Azure Speech Services进行语音合成(TTS)
   - 将合成的语音通过MQTT发送回客户端

2. **用户客户端** (user.py)
   - 提供语音录制功能
   - 通过MQTT发送音频数据
   - 接收并播放AI回复的语音

## 技术栈

- **MQTT**: 用于实现客户端与服务端之间的通信
- **Azure Speech Services**: 提供语音识别(STT)和语音合成(TTS)服务
- **Claude AI**: 提供智能对话服务
- **PyAudio**: 用于音频录制和播放
- **Python**: 主要开发语言

## 环境要求

需要在环境变量文件(.env)中配置以下参数：
- SPEECH_KEY: Azure语音服务密钥
- SPEECH_REGION: Azure服务区域
- API_KEY: Claude AI API密钥
- BASE_URL: Claude AI API基础URL
- MQTT_BROKER: MQTT服务器地址
- MQTT_PORT: MQTT服务器端口

## 使用方法

1. 启动服务端：
```bash
python voice_ai_chatbot.py
```

2. 启动客户端：
```bash
python user.py
```

3. 操作说明：
   - 按空格键开始录音
   - 再次按空格键结束录音
   - 系统会自动处理语音并通过AI生成回复
   - AI的语音回复会自动播放

## 通信流程

1. 用户通过客户端录制语音
2. 语音数据通过MQTT发送至服务端(topic: voice/audio)
3. 服务端进行语音识别
4. 识别结果发送给Claude AI处理
5. AI回复转换为语音
6. 语音数据通过MQTT发送回客户端(topic: voice/response)
7. 客户端接收并播放语音回复

## 注意事项

- 确保MQTT服务器正常运行
- 录音时间不能太短（小于0.3秒的录音会被忽略）
- 需要稳定的网络连接以确保服务正常运行
```
