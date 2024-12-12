# 语音AI聊天机器人

这是一个基于Azure语音服务和OpenAI的语音聊天机器人项目，支持实时语音对话。用户可以通过语音输入进行交谈，系统会将语音转换为文字，通过AI处理后返回语音回复。

## 功能特点

- 实时语音识别和转写
- AI自然语言处理（基于GPT-3.5）
- 文字转语音回复
- 基于MQTT的实时音频流传输
- 支持中文语音交互
- 简单的用户界面，使用空格键控制录音

## 系统要求

- Python 3.7+
- Windows操作系统（当前版本使用了msvcrt库）
- 麦克风和扬声器
- 网络连接

## 依赖项

```plaintext
azure-cognitiveservices-speech
openai
paho-mqtt
python-dotenv
pyaudio
wave
```

## 环境配置

1. 克隆项目并安装依赖：
```bash
git clone https://github.com/youjiaping123/voiceAI
cd voiceAI
pip install -r requirements.txt
```

2. 创建`.env`文件并配置以下环境变量：
```plaintext
SPEECH_KEY=你的Azure语音服务密钥          
SPEECH_REGION=Azure服务区域
API_KEY=OpenAI API密钥
BASE_URL=OpenAI API地址
MQTT_BROKER=MQTT服务器地址
MQTT_PORT=MQTT服务器端口
```

## 使用说明

1. 首先启动语音AI服务端：
```bash
python voice_ai_chatbot.py
```

2. 然后启动用户客户端：
```bash
python user.py
```

3. 操作方法：
   - 按空格键开始录音
   - 再次按空格键停止录音
   - 系统会自动处理语音并返回AI的语音回复
   - 使用Ctrl+C退出程序

## 系统架构

### 核心组件

1. **语音服务端 (voice_ai_chatbot.py)**
   - 处理语音识别
   - 与OpenAI API交互
   - 生成语音回复
   - 管理MQTT消息通信

2. **用户客户端 (user.py)**
   - 录制用户语音
   - 通过MQTT发送音频流
   - 接收并播放AI回复
   - 提供用户交互界面

### 数据流

1. 用户语音输入 → MQTT音频流传输
2. 语音识别 → 文字转换
3. AI处理 → 生成回复
4. 文字转语音 → MQTT传输
5. 客户端接收 → 播放语音回复

## 注意事项

- 确保麦克风和扬声器正常工作
- 需要稳定的网络连接
- Azure和OpenAI服务需要有效的API密钥
- MQTT服务器需要正确配置和运行

## 错误处理

系统包含完整的错误处理和日志记录机制：
- 所有操作都有时间戳日志
- 网络连接异常处理
- 音频设备错误处理
- API调用重试机制