import asyncio
from email.message import EmailMessage
from typing import Optional
from app.config import settings


async def send_email(
    to: str,
    subject: str,
    content: str,
    html_content: Optional[str] = None
) -> bool:
    """
    异步发送电子邮件
    
    Args:
        to: 收件人邮箱
        subject: 邮件主题
        content: 邮件正文（纯文本）
        html_content: 邮件正文（HTML格式，可选）
        
    Returns:
        bool: 发送成功返回True，失败返回False
    """
    # 构建邮件消息
    msg = EmailMessage()
    msg["From"] = settings.smtp_username
    msg["To"] = to
    msg["Subject"] = f"{settings.email_subject_prefix}{subject}"
    
    # 设置邮件正文
    msg.set_content(content)
    
    # 如果提供了HTML内容，添加为替代内容
    if html_content:
        msg.add_alternative(html_content, subtype="html")
    
    try:
        import aiosmtplib
        
        # 连接SMTP服务器并发送邮件
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_server,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=True,  # QQ邮箱要求使用TLS
        )
        
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


async def send_verification_code_email(email: str, code: str, purpose: str) -> bool:
    """
    发送验证码邮件
    
    Args:
        email: 收件人邮箱
        code: 验证码
        purpose: 验证码用途（register, login, reset_password）
        
    Returns:
        bool: 发送成功返回True，失败返回False
    """
    # 根据用途生成不同的邮件内容
    purpose_map = {
        "register": "注册",
        "login": "登录",
        "reset_password": "重置密码"
    }
    
    purpose_text = purpose_map.get(purpose, "验证")
    
    # 纯文本内容
    text_content = f"""
    您的{purpose_text}验证码：{code}
    
    该验证码有效期为{settings.verification_code_expire_minutes}分钟，请在有效期内使用。
    
    请勿将验证码泄露给他人，如非本人操作，请忽略此邮件。
    
    --- XBots Agent
    """
    
    # HTML内容
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>验证码</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .container {{ background-color: #f9f9f9; border-radius: 8px; padding: 20px; }}
            .code {{ font-size: 24px; font-weight: bold; color: #4CAF50; margin: 20px 0; }}
            .note {{ font-size: 14px; color: #666; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>您的{purpose_text}验证码</h2>
            <p>尊敬的用户：</p>
            <p>您好！您正在进行{purpose_text}操作，您的验证码是：</p>
            <div class="code">{code}</div>
            <p>该验证码有效期为{settings.verification_code_expire_minutes}分钟，请在有效期内使用。</p>
            <p class="note">请勿将验证码泄露给他人，如非本人操作，请忽略此邮件。</p>
            <p>--- XBots Agent</p>
        </div>
    </body>
    </html>
    """
    
    return await send_email(
        to=email,
        subject=f"{purpose_text}验证码",
        content=text_content,
        html_content=html_content
    )