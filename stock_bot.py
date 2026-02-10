import pandas as pd
from groq import Groq
import telebot
import os
from datetime import datetime
import random

WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

MOCK_PRICES = {
    'AAPL': 228.50,
    'MSFT': 425.30,
    'GOOGL': 175.80,
    'NVDA': 135.60,
    'TSLA': 345.20
}

def create_report(symbol):
    price = MOCK_PRICES[symbol]
    change = random.uniform(-2, 3)
    rsi = random.uniform(40, 65)
    
    signals = []
    if rsi < 45:
        signals.append(f"🟢 RSI: {rsi:.1f}")
    elif rsi > 60:
        signals.append(f"🔴 RSI: {rsi:.1f}")
    else:
        signals.append(f"⚪ RSI: {rsi:.1f}")
    
    if change > 1:
        signals.append("📈 Pozitif momentum")
    elif change < -1:
        signals.append("📉 Negatif momentum")
    
    prompt = f"""Kısa borsa analizi yap (max 50 kelime):

Hisse: {symbol}
Fiyat: ${price:.2f} 
Değişim: {change:+.2f}%
RSI: {rsi:.1f}

Şu formatta yaz:
📊 DURUM: (1 cümle trend analizi)
💡 ÖNERİ: AL/TUT/SAT + kısa açıklama
⚠️ RİSK: Düşük/Orta/Yüksek + sebep"""

    try:
        print(f"🤖 {symbol} için AI analizi yapılıyor...")
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-70b-versatile",
            temperature=0.3,
            max_tokens=200
        )
        ai = response.choices[0].message.content
        print(f"✅ {symbol} AI analizi başarılı")
    except Exception as e:
        print(f"❌ {symbol} AI hatası: {type(e).__name__}: {str(e)}")
        ai = f"AI analizi yapılamadı: {type(e).__name__}"
    
    return f"""
━━━━━━━━━━━━━━━━━━━━
*{symbol}*
💵 ${price:.2f} ({change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━

🤖 *AI ANALİZ:*
{ai}

📈 *SİNYALLER:*
{chr(10).join('• ' + s for s in signals)}
"""

def main():
    print(f"🚀 Bot başlatıldı")
    print(f"📋 GROQ API Key ilk 10 karakter: {GROQ_API_KEY[:10] if GROQ_API_KEY else 'YOK!'}")
    
    all_reports = []
    for symbol in WATCHLIST:
        try:
            report = create_report(symbol)
            all_reports.append(report)
            print(f"✅ {symbol}")
        except Exception as e:
            print(f"❌ {symbol}: {e}")
            all_reports.append(f"❌ *{symbol}*: Hata")
    
    header = f"""
📊 *NASDAQ TEST RAPOR*
📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}

{', '.join(WATCHLIST)}
"""
    
    message = header + '\n'.join(all_reports) + "\n\n🤖 _Test versiyonu_"
    
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='Markdown')
        print("✅ Telegram'a gönderildi!")
    except Exception as e:
        print(f"❌ Telegram: {e}")

if __name__ == '__main__':
    main()
