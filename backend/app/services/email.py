"""
Сервис для отправки email уведомлений.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from loguru import logger


class EmailService:
    """Сервис для отправки email."""
    
    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email or smtp_user
        self.use_tls = use_tls
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Отправка email.
        
        Args:
            to_email: Email получателя
            subject: Тема письма
            html_content: HTML содержимое
            text_content: Текстовое содержимое (опционально)
        
        Returns:
            bool: True если успешно
        """
        if not self.smtp_user or not self.smtp_password or not self.from_email:
            logger.error("❌ SMTP не настроен. Отправка email невозможна.")
            return False
        
        try:
            # Создание письма
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to_email
            
            # Текстовая версия
            if text_content:
                part1 = MIMEText(text_content, "plain", "utf-8")
                msg.attach(part1)
            
            # HTML версия
            part2 = MIMEText(html_content, "html", "utf-8")
            msg.attach(part2)
            
            # Отправка
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, to_email, msg.as_string())
            
            logger.info(f"✅ Email отправлен: {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки email: {e}")
            return False
    
    def send_password_reset(
        self,
        to_email: str,
        reset_link: str,
        user_name: Optional[str] = None,
    ) -> bool:
        """
        Отправка письма для сброса пароля.
        
        Args:
            to_email: Email получателя
            reset_link: Ссылка для сброса пароля
            user_name: Имя пользователя (опционально)
        
        Returns:
            bool: True если успешно
        """
        subject = "🔑 Сброс пароля MegaSharkAI"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #1e293b;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 12px;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .logo {{
                    width: 80px;
                    height: 80px;
                    background: white;
                    border-radius: 16px;
                    margin: 0 auto 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 40px;
                    font-weight: bold;
                    color: #667eea;
                }}
                h1 {{
                    color: white;
                    font-size: 28px;
                    margin: 0 0 10px 0;
                }}
                .subtitle {{
                    color: rgba(255, 255, 255, 0.9);
                    font-size: 16px;
                    margin-bottom: 30px;
                }}
                .content {{
                    background: white;
                    border-radius: 12px;
                    padding: 30px;
                    margin-top: -20px;
                    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-decoration: none;
                    padding: 14px 40px;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 16px;
                    margin: 20px 0;
                    transition: transform 0.2s;
                }}
                .button:hover {{
                    transform: translateY(-2px);
                }}
                .link {{
                    color: #667eea;
                    word-break: break-all;
                    font-size: 12px;
                }}
                .warning {{
                    background: #fef3c7;
                    border-left: 4px solid #f59e0b;
                    padding: 15px;
                    border-radius: 6px;
                    margin: 20px 0;
                    font-size: 14px;
                    color: #92400e;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #e2e8f0;
                    font-size: 12px;
                    color: #64748b;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="logo">🦈</div>
                <h1>MegaSharkAI</h1>
                <p class="subtitle">Сброс пароля</p>
            </div>
            
            <div class="content">
                <p>Здравствуйте{", " + user_name if user_name else ""}!</p>
                
                <p>Вы запросили сброс пароля для вашего аккаунта MegaSharkAI.</p>
                
                <p style="text-align: center;">
                    <a href="{reset_link}" class="button">🔑 Сбросить пароль</a>
                </p>
                
                <p style="text-align: center;">
                    <a href="{reset_link}" class="link">{reset_link}</a>
                </p>
                
                <div class="warning">
                    <strong>⚠️ Важно:</strong> Ссылка действительна в течение 1 часа.<br>
                    Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.
                </div>
                
                <div class="footer">
                    <p>Это письмо было отправлено автоматически, пожалуйста, не отвечайте на него.</p>
                    <p>© 2024 MegaSharkAI. Все права защищены.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
Здравствуйте{", " + user_name if user_name else ""}!

Вы запросили сброс пароля для вашего аккаунта MegaSharkAI.

Для сброса пароля перейдите по ссылке:
{reset_link}

Ссылка действительна в течение 1 часа.

Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.

---
MegaSharkAI - AI-ассистент для продавцов маркетплейсов
        """
        
        return self.send_email(to_email, subject, html_content, text_content)


# Глобальный экземпляр (будет инициализирован в main.py)
email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Получение сервиса email."""
    return email_service
