from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # 群聊与触发
    FEISHU_CHAT_ID: str = Field(default="oc_cd5f1d54c1a5349c06ac0d1dd0050a55")
    BASE_URL: str | None = Field(default=None)
    WIKI_URL: str | None = Field(default=None)
    TRIGGER_KEYWORD: str = Field(default="AI助手问题单日报")


    # 轮询
    POLL_INTERVAL_SEC: int = Field(default=5)
    MAX_MESSAGES_PER_POLL: int = Field(default=20)
    ORDER: str = Field(default="desc")

    # 去重
    STATE_DIR: str = Field(default="./state")
    PROCESSED_IDS_FILE: str = Field(default="processed_msg_ids.json")

    # 输出
    OUTPUT_DIR: str = Field(default="./output")
    HTML_FILENAME: str = Field(default="ai_assistant_daily_report.html")
    PNG_FILENAME: str = Field(default="ai_assistant_daily_report.png")

    # 截图
    VIEWPORT_WIDTH: int = Field(default=1600)
    VIEWPORT_HEIGHT: int = Field(default=900)
    FULL_PAGE: bool = Field(default=True)

    # lark-cli
    LARK_CLI_CMD: str = Field(default="lark-cli")

    # Wiki 信息
    WIKI_TOKEN_ORIGIN: str = Field(default="DIrhwrspsim0Wmk3f8kcOba2n8e")
    TABLE_ID: str = Field(default="tblOQtVpkDcTwqpc")
    VIEW_ID: str = Field(default="vewb0suZqs")

    @property
    def state_path(self) -> Path:
        p = Path(self.STATE_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p / self.PROCESSED_IDS_FILE

    @property
    def output_dir_path(self) -> Path:
        p = Path(self.OUTPUT_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def html_path(self) -> Path:
        return self.output_dir_path / self.HTML_FILENAME

    @property
    def png_path(self) -> Path:
        return self.output_dir_path / self.PNG_FILENAME


settings = Settings()
