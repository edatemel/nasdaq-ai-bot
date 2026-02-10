import requests
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from groq import Groq
import telebot
import os
from datetime import datetime, timedelta
import time

# 📊 TAKİP EDİLECEK HİSSELER
WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']

# 🔑 API Bilgileri
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')

# 🤖 Bot ve AI istemcileri
bot = telebot.TeleBot(TELEGRAM_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

def fetch_stock_data(symbol):
    """Finnhub ile hisse verilerini çek"""
    print(f"📥 {symbol} verisi çekiliyor...")
    
    try:
        # Son 90 günlük veri için tarih hesapla
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        # Unix timestamp'e çevir
        end_ts = int(end_date.timestamp())
        start_ts = int(start_date.timestamp())
        
        # Finnhub API - Candle data
        url = f'https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=D&from={start_ts}&to={end_ts}&token={FINNHUB_API_KEY}'
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('s') != 'ok':
            raise Exception(f"API hatası: {data.get('s', 'Bilinmeyen hata')}")
        
        # DataFrame'e dönüştür
        df = pd.DataFrame({
            'Open': data['o'],
            'High': data['h'],
            'Low': data['l'],
            'Close': data['c'],
            'Volume': data['v']
        })
        
        # Tarihleri ekle
        df.index = pd.to_datetime(data['t'], unit='s')
        
        if df.empty or len(df) < 50:
            raise Exception(f"Yetersiz veri: {len(df)} gün")
        
        # Teknik göstergeler
        df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()
        df['SMA_20'] = SMAIndicator(close=df['Close'], window=20).sma_indicator()
        df['SMA_50'] = SMAIndicator(close=df['Close'], window=50).sma_indicator()
        
        print(f"✅ {symbol} verisi başarıyla çekildi ({len(df)} günlük veri)")
        return df
        
    except Exception as e:
        print(f"❌ {symbol} veri hatası: {e}")
        raise

def generate_signals(df):
    """Teknik sinyalleri tespit et"""
    latest = df.iloc[-1]
    signals = []
    
    # RSI Analizi
    if pd.notna(latest['RSI']):
        if latest['RSI'] < 30:
            signals.append(f"🟢 RSI aşırı satım: {latest['RSI']:.1f}")
        elif latest['RSI'] > 70:
            signals.append(f"🔴 RSI aşırı alım: {latest['RSI']:.1f}")
        else:
            signals.append(f"⚪ RSI nötr: {latest['RSI']:.1f}")
    
    # Moving Average Trend
    if pd.notna(latest['SMA_50']) and pd.notna(latest['SMA_20']):
        if latest['Close'] > latest['SMA_50']:
            if latest['Close'] > latest['SMA_20']:
                signals.append("📈 Güçlü yükseliş trendi")
            else:
                signals.append("📊 Yükseliş trendi")
        else:
            signals.append("📉 Fiyat 50 MA altında")
    
    # Hacim
    avg_volume = df['Volume'].tail(20).mean()
    volume_ratio = latest['Volume'] / avg_volume
    if volume_ratio > 1.5:
        signals.append(f"🔊 Yüksek hacim: {volume_ratio:.1f}x")
    
    return signals

def analyze_with_ai(symbol, df, signals):
    """AI ile analiz"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change_pct = ((latest['Close'] / prev['Close'] - 1) * 100)
    
    prompt = f"""Kısa borsa analizi yap (max 80 kelime):

{symbol}: ${latest['Close']:.2f} ({change_pct:+.2f}%)
RSI: {latest['RSI']:.1f}
Sinyaller: {', '.join(signals)}

Format:
📊 Durum: 
💡 Öneri: AL/TUT/SAT
⚠️ Risk: Düşük/Orta/Yüksek"""

    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-70b-versatile",
            temperature=0.3,
            max_tokens=200
        )
        return response.choices[0].message.content
    except:
        return "AI analizi yapılamadı"

def create_report(symbol, df):
    """Rapor oluştur"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change_pct = ((latest['Close'] / prev['Close'] - 1) * 100)
    
    signals = generate_signals(df)
    ai_analysis = analyze_with_ai(symbol, df, signals)
    
    report = f"""
━━━━━━━━━━━━━━━━━━━━
*{symbol}*
💵 ${latest['Close']:.2f} ({change_pct:+.2f}%)
━━━━━━━━━━━━━━━━━━━━

🤖 *AI ANALİZ:*
{ai_analysis}

📈 *SİNYALLER:*
{chr(10).join('• ' + s for s in signals)}
"""
    return report

def main():
    """Ana fonksiyon"""
    print(f"🚀 Bot başlatıldı - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    all_reports = []
    
    for i, symbol in enumerate(WATCHLIST):
        try:
            if i > 0:
                time.sleep(1)  # Rate limit
            
            df = fetch_stock_data(symbol)
            report = create_report(symbol, df)
            all_reports.append(report)
            print(f"✅ {symbol} tamamlandı")
            
        except Exception as e:
            print(f"❌ {symbol} hatası: {e}")
            all_reports.append(f"❌ *{symbol}*: Veri çekilemedi")
    
    # Telegram'a gönder
    header = f"""
📊 *NASDAQ GÜNLÜK RAPOR*
📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}

Hisseler: {', '.join(WATCHLIST)}
"""
    
    full_message = header + '\n'.join(all_reports)
    full_message += "\n\n━━━━━━━━━━━━━━━━━━━━\n🤖 _Otomatik rapor_"
    
    try:
        bot.send_message(TELEGRAM_CHAT_ID, full_message, parse_mode='Markdown')
        print("✅ Telegram'a gönderildi!")
    except Exception as e:
        print(f"❌ Telegram hatası: {e}")
    
    print(f"🏁 Tamamlandı - {len(all_reports)} hisse")

if __name__ == '__main__':
    main()
