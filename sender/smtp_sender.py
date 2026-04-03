"""
smtp_sender.py

通过 SMTP 发送 HTML 邮件，支持 163 / Gmail / QQ 三种服务商。
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


SMTP_CONFIG = {
    "163":   {"host": "smtp.163.com",   "port": 465, "ssl": True},
    "gmail": {"host": "smtp.gmail.com", "port": 587, "ssl": False},
    "qq":    {"host": "smtp.qq.com",    "port": 465, "ssl": True},
}


def send_email(
    html_content: str,
    from_addr: str,
    password: str,
    to_addr: str,
    provider: str = "163",
):
    """
    发送 HTML 格式邮件。

    Args:
        html_content: 渲染好的 HTML 字符串
        from_addr: 发件邮箱地址
        password: 发件邮箱授权码（非登录密码）
        to_addr: 收件邮箱地址
        provider: smtp_provider（163 / gmail / qq）

    Raises:
        ValueError: 不支持的 provider
        smtplib.SMTPException: 发送失败
    """
    if str(provider) not in SMTP_CONFIG:
        raise ValueError(f"不支持的 smtp_provider: {provider}，可选：{list(SMTP_CONFIG.keys())}")

    cfg = SMTP_CONFIG[str(provider)]
    date_str = datetime.now().strftime("%Y-%m-%d")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📄 每日论文推送 · {date_str}"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    if cfg["ssl"]:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"]) as server:
            server.login(from_addr, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.starttls()
            server.login(from_addr, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())

    print(f"[OK] 邮件已发送至 {to_addr}")
