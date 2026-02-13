import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from groq import Groq
import telebot
import os
from datetime import datetime
import time

WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

def fetch_stock_data(symbol):
    """Gerçek hisse verisi çek"""
    print(f"📥 {symbol} verisi çekiliyor...")
    
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period='3mo', interval='1d')
        
        if df.empty or len(df) < 50:
            raise Exception(f"Yetersiz veri: {len(df)} gün")
        
        # Teknik göstergeler
        df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()
        df['SMA_20'] = SMAIndicator(close=df['Close'], window=20).sma_indicator()
        df['SMA_50'] = SMAIndicator(close=df['Close'], window=50).sma_indicator()
        
        print(f"✅ {symbol} - {len(df)} günlük veri çekildi")
        return df
        
    except Exception as e:
        print(f"❌ {symbol} veri hatası: {e}")
        raise

def generate_signals(df):
    """Teknik sinyaller"""
    latest = df.iloc[-1]
    signals = []
    
    # RSI
    if pd.notna(latest['RSI']):
        if latest['RSI'] < 30:
            signals.append(f"🟢 RSI: {latest['RSI']:.1f} (Aşırı satım)")
        elif latest['RSI'] > 70:
            signals.append(f"🔴 RSI: {latest['RSI']:.1f} (Aşırı alım)")
        else:
            signals.append(f"⚪ RSI: {latest['RSI']:.1f} (Nötr)")
    
    # Moving Averages
    if pd.notna(latest['SMA_50']) and pd.notna(latest['SMA_20']):
        if latest['Close'] > latest['SMA_50'] and latest['Close'] > latest['SMA_20']:
            signals.append("📈 Güçlü yükseliş trendi")
        elif latest['Close'] > latest['SMA_50']:
            signals.append("📊 Yükseliş trendi")
        else:
            signals.append("📉 Düşüş eğilimi")
    
    # Volume
    avg_volume = df['Volume'].tail(20).mean()
    volume_ratio = latest['Volume'] / avg_volume
    if volume_ratio > 1.5:
        signals.append(f"🔊 Yüksek hacim: {volume_ratio:.1f}x")
    
    return signals

def analyze_with_ai(symbol, df, signals):
    """GROQ AI analizi"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change = ((latest['Close'] / prev['Close'] - 1) * 100)
    
    # 7 günlük trend
    week_ago = df.iloc[-7] if len(df) >= 7 else prev
    week_change = ((latest['Close'] / week_ago['Close'] - 1) * 100)
    
    prompt = f"""Sen bir profesyonel hisse senedi analistisin. Aşağıdaki verilere göre kısa ve net analiz yap:

Hisse: {symbol}
Güncel Fiyat: ${latest['Close']:.2f}
Günlük Değişim: {change:+.2f}%
Haftalık Değişim: {week_change:+.2f}%
RSI (14): {latest['RSI']:.1f}
20 Günlük Ortalama: ${latest['SMA_20']:.2f}
50 Günlük Ortalama: ${latest['SMA_50']:.2f}

Sinyaller: {', '.join(signals)}

SADECE şu formatta yaz (max 80 kelime):

📊 DURUM: [1 cümle - güncel trend ve momentum]
💡 ÖNERİ: AL/TUT/SAT [kısa açıklama]
⚠️ RİSK: Düşük/Orta/Yüksek [sebep]
🎯 DİKKAT: [önemli destek/direnç seviyesi varsa]"""

    try:
        print(f"🤖 {symbol} AI analizi yapılıyor...")
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=250
        )
        ai_text = response.choices[0].message.content
        print(f"✅ {symbol} AI analizi tamamlandı")
        return ai_text
        
    except Exception as e:
        print(f"❌ {symbol} AI hatası: {e}")
        return "AI analizi yapılamadı"

def create_report(symbol, df):
    """Rapor oluştur"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change = ((latest['Close'] / prev['Close'] - 1) * 100)
    
    signals = generate_signals(df)
    ai_analysis = analyze_with_ai(symbol, df, signals)
    
    return f"""
━━━━━━━━━━━━━━━━━━━━
*{symbol}*
💵 ${latest['Close']:.2f} ({change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━

🤖 *AI ANALİZ:*
{ai_analysis}

📈 *TEKNİK SİNYALLER:*
{chr(10).join('• ' + s for s in signals)}
"""

def main():
    """Ana fonksiyon"""
    print(f"🚀 Bot başlatıldı - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    all_reports = []
    
    for i, symbol in enumerate(WATCHLIST):
        try:
            if i > 0:
                time.sleep(2)  # Rate limit
            
            df = fetch_stock_data(symbol)
            report = create_report(symbol, df)
            all_reports.append(report)
            print(f"✅ {symbol} tamamlandı")
            
        except Exception as e:
            print(f"❌ {symbol} başarısız: {e}")
            all_reports.append(f"❌ *{symbol}*: Veri çekilemedi")
    
    # Telegram mesajı
    header = f"""
📊 *NASDAQ GÜNLÜK ANALİZ*
📅 {datetime.now().strftime('%d %B %Y - %H:%M')}

Takip edilen: {', '.join(WATCHLIST)}
"""
    
    message = header + '\n'.join(all_reports)
    message += "\n\n━━━━━━━━━━━━━━━━━━━━\n🤖 _Otomatik üretilmiştir_"
    
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='Markdown')
        print("✅ Telegram'a gönderildi!")
    except Exception as e:
        print(f"❌ Telegram hatası: {e}")
    
    print(f"🏁 Tamamlandı - {len(all_reports)} hisse analiz edildi")

if __name__ == '__main__':
    main()
