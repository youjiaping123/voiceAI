class Config:
    # 音频设置
    AUDIO_CHUNK_SIZE = 1024
    AUDIO_FORMAT = pyaudio.paInt16
    AUDIO_CHANNELS = 1
    AUDIO_RATE = 16000
    
    # MQTT设置
    MQTT_KEEPALIVE = 60
    MQTT_QOS = 1
    
    # 重试设置
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    
    # 路径设置
    TEMP_DIR = "temp"
    LOG_DIR = "logs" 