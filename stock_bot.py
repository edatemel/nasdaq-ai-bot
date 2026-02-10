import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from groq import Groq
import telebot
import os
from datetime import datetime

# 📊 TAKİP EDİLECEK HİSSELER (İstediğin gibi değiştirebilirsin)
WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']

# 🔑 API Bilgileri (GitHub Secrets'tan gelecek)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# 🤖 Bot ve AI istemcileri
bot = telebot.TeleBot(TELEGRAM_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

def fetch_stock_data(symbol):
    """Hisse verilerini çek ve teknik göstergeleri hesapla"""
    print(f"📥 {symbol} verisi çekiliyor...")
    
    stock = yf.Ticker(symbol)
    df = stock.history(period='3mo', interval='1d')
    
    # Teknik göstergeler - ta kütüphanesi ile
    df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()
    df['SMA_20'] = SMAIndicator(close=df['Close'], window=20).sma_indicator()
    df['SMA_50'] = SMAIndicator(close=df['Close'], window=50).sma_indicator()
    
    return df

def generate_signals(df):
    """Teknik sinyalleri tespit et"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    signals = []
    
    # RSI Analizi
    if latest['RSI'] < 30:
        signals.append(f"🟢 RSI aşırı satım bölgesinde: {latest['RSI']:.1f} (Alım fırsatı olabilir)")
    elif latest['RSI'] > 70:
        signals.append(f"🔴 RSI aşırı alım bölgesinde: {latest['RSI']:.1f} (Düzeltme gelebilir)")
    else:
        signals.append(f"⚪ RSI nötr: {latest['RSI']:.1f}")
    
    # Moving Average Trend
    if latest['Close'] > latest['SMA_50']:
        if latest['Close'] > latest['SMA_20']:
            signals.append("📈 Güçlü yükseliş trendi (20 ve 50 MA üstünde)")
        else:
            signals.append("📊 Yükseliş trendi devam ediyor (50 MA üstünde)")
    else:
        signals.append("📉 Fiyat 50 MA altında (zayıf trend)")
    
    # Hacim Analizi
    avg_volume = df['Volume'].tail(20).mean()
    volume_ratio = latest['Volume'] / avg_volume
    if volume_ratio > 1.5:
        signals.append(f"🔊 Yüksek hacim: {volume_ratio:.1f}x ortalama")
    
    return signals

def analyze_with_ai(symbol, df, signals):
    """AI ile detaylı analiz yap"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change_pct = ((latest['Close'] / prev['Close'] - 1) * 100)
    
    prompt = f"""Sen bir borsa analiz uzmanısın. Aşağıdaki verilere göre kısa ve net bir analiz yap:

Hisse: {symbol}
Güncel Fiyat: ${latest['Close']:.2f}
Günlük Değişim: {change_pct:+.2f}%
Hacim: {latest['Volume']:,.0f}

Teknik Göstergeler:
- RSI (14): {latest['RSI']:.2f}
- Fiyat/SMA20: ${latest['Close']:.2f} / ${latest['SMA_20']:.2f}
- Fiyat/SMA50: ${latest['Close']:.2f} / ${latest['SMA_50']:.2f}

Tespit Edilen Sinyaller:
{chr(10).join('• ' + s for s in signals)}

Lütfen şu formatta 100 kelimeyi geçmeyecek şekilde analiz yap:

📊 GENEL DURUM: (1 cümle - trend yönü)
💡 ÖNERİ: AL / TUT / SAT + kısa açıklama
⚠️ RİSK: Düşük/Orta/Yüksek + neden
🎯 DİKKAT: Önemli fiyat seviyesi varsa belirt

Türkçe yaz, net ol, abartma."""

    response = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-70b-versatile",
        temperature=0.3,
        max_tokens=400
    )
    
    return response.choices[0].message.content

def create_report(symbol, df):
    """Tek bir hisse için rapor oluştur"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change_pct = ((latest['Close'] / prev['Close'] - 1) * 100)
    
    # Sinyaller
    signals = generate_signals(df)
    
    # AI Analizi
    ai_analysis = analyze_with_ai(symbol, df, signals)
    
    # Rapor formatı
    report = f"""
━━━━━━━━━━━━━━━━━━━━
*{symbol}* 
💵 ${latest['Close']:.2f} ({change_pct:+.2f}%)
━━━━━━━━━━━━━━━━━━━━

🤖 *AI ANALİZ:*
{ai_analysis}

📈 *TEKNİK SİNYALLER:*
{chr(10).join('• ' + s for s in signals)}
"""
    
    return report

def main():
    """Ana bot fonksiyonu"""
    print(f"🚀 Bot başlatıldı - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    all_reports = []
    
    for symbol in WATCHLIST:
        try:
            # Veri çek
            df = fetch_stock_data(symbol)
            
            # Rapor oluştur
            report = create_report(symbol, df)
            all_reports.append(report)
            
            print(f"✅ {symbol} tamamlandı")
            
        except Exception as e:
            print(f"❌ {symbol} hatası: {e}")
            all_reports.append(f"❌ *{symbol}*: Veri çekilemedi")
    
    # Telegram'a gönder
    header = f"""
📊 *NASDAQ GÜNLÜK RAPOR*
📅 {datetime.now().strftime('%d %B %Y - %H:%M')}

Takip edilen hisseler: {', '.join(WATCHLIST)}
"""
    
    full_message = header + '\n'.join(all_reports)
    full_message += "\n\n━━━━━━━━━━━━━━━━━━━━\n🤖 _Bu rapor tamamen otomatik üretilmiştir_"
    
    try:
        bot.send_message(TELEGRAM_CHAT_ID, full_message, parse_mode='Markdown')
        print("✅ Telegram'a gönderildi!")
    except Exception as e:
        print(f"❌ Telegram hatası: {e}")
    
    print(f"🏁 İşlem tamamlandı - {len(all_reports)} hisse analiz edildi")

if __name__ == '__main__':
    main()
