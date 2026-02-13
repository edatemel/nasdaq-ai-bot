import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from groq import Groq
import telebot
import os
from datetime import datetime
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import base64

WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

def fetch_stock_data(symbol):
    """yfinance ile veri çek"""
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
        
        print(f"✅ {symbol} - {len(df)} günlük veri")
        return df
        
    except Exception as e:
        print(f"❌ {symbol} veri hatası: {e}")
        raise

def create_chart(symbol, df):
    """Profesyonel grafik"""
    print(f"📊 {symbol} grafik oluşturuluyor...")
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    fig.patch.set_facecolor('#0e1117')
    
    # Fiyat
    ax1.set_facecolor('#1a1d24')
    ax1.plot(df.index, df['Close'], color='#00d4ff', linewidth=2, label='Fiyat')
    ax1.plot(df.index, df['SMA_20'], color='#ff9500', linewidth=1.5, alpha=0.7, label='SMA 20')
    ax1.plot(df.index, df['SMA_50'], color='#ff3b30', linewidth=1.5, alpha=0.7, label='SMA 50')
    ax1.fill_between(df.index, df['Close'], alpha=0.1, color='#00d4ff')
    ax1.set_ylabel('Fiyat ($)', color='white', fontsize=12)
    ax1.tick_params(colors='white')
    ax1.legend(loc='upper left', facecolor='#1a1d24', edgecolor='white', labelcolor='white')
    ax1.grid(True, alpha=0.1, color='white')
    ax1.set_title(f'{symbol} - Teknik Analiz', color='white', fontsize=16, fontweight='bold', pad=20)
    
    # RSI
    ax2.set_facecolor('#1a1d24')
    ax2.plot(df.index, df['RSI'], color='#bf5af2', linewidth=2)
    ax2.axhline(y=70, color='#ff3b30', linestyle='--', alpha=0.5)
    ax2.axhline(y=30, color='#34c759', linestyle='--', alpha=0.5)
    ax2.fill_between(df.index, df['RSI'], 50, where=(df['RSI']>=50), alpha=0.3, color='#34c759')
    ax2.fill_between(df.index, df['RSI'], 50, where=(df['RSI']<50), alpha=0.3, color='#ff3b30')
    ax2.set_ylabel('RSI', color='white', fontsize=12)
    ax2.tick_params(colors='white')
    ax2.set_ylim([0, 100])
    ax2.grid(True, alpha=0.1, color='white')
    
    # Hacim
    ax3.set_facecolor('#1a1d24')
    colors = ['#34c759' if c >= o else '#ff3b30' for c, o in zip(df['Close'], df['Open'])]
    ax3.bar(df.index, df['Volume'], color=colors, alpha=0.5, width=0.8)
    ax3.set_ylabel('Hacim', color='white', fontsize=12)
    ax3.tick_params(colors='white')
    ax3.grid(True, alpha=0.1, color='white')
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor='#0e1117')
    buf.seek(0)
    plt.close()
    
    img_base64 = base64.b64encode(buf.getvalue()).decode()
    buf.seek(0)
    
    print(f"✅ {symbol} grafik hazır")
    return buf, img_base64

def generate_signals(df):
    latest = df.iloc[-1]
    signals = []
    
    if pd.notna(latest['RSI']):
        if latest['RSI'] < 30:
            signals.append(f"🟢 RSI: {latest['RSI']:.1f} (Aşırı satım)")
        elif latest['RSI'] > 70:
            signals.append(f"🔴 RSI: {latest['RSI']:.1f} (Aşırı alım)")
        else:
            signals.append(f"⚪ RSI: {latest['RSI']:.1f}")
    
    if pd.notna(latest['SMA_50']) and pd.notna(latest['SMA_20']):
        if latest['Close'] > latest['SMA_50'] and latest['Close'] > latest['SMA_20']:
            signals.append("📈 Güçlü yükseliş")
        elif latest['Close'] > latest['SMA_50']:
            signals.append("📊 Yükseliş trendi")
        else:
            signals.append("📉 Düşüş eğilimi")
    
    avg_vol = df['Volume'].tail(20).mean()
    vol_ratio = latest['Volume'] / avg_vol
    if vol_ratio > 1.5:
        signals.append(f"🔊 Yüksek hacim: {vol_ratio:.1f}x")
    
    return signals

def analyze_with_ai(symbol, df, signals, chart_base64):
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change = ((latest['Close'] / prev['Close'] - 1) * 100)
    
    week_ago = df.iloc[-7] if len(df) >= 7 else prev
    week_change = ((latest['Close'] / week_ago['Close'] - 1) * 100)
    
    prompt = f"""Yukarıdaki GRAFİĞİ incele ve teknik analiz yap:

{symbol}: ${latest['Close']:.2f} ({change:+.2f}%)
Haftalık: {week_change:+.2f}%
RSI: {latest['RSI']:.1f}
SMA 20/50: ${latest['SMA_20']:.2f} / ${latest['SMA_50']:.2f}
Sinyaller: {', '.join(signals)}

Grafikte:
- Trend nasıl?
- Destek/direnç nerede?
- Formasyon var mı?

Format (max 100 kelime):
📊 GRAFİK: [ne görüyorsun]
💡 ÖNERİ: AL/TUT/SAT [sebep]
⚠️ RİSK: Düşük/Orta/Yüksek
🎯 HEDEF: [fiyat seviyeleri]"""

    try:
        print(f"🤖 {symbol} AI analizi...")
        response = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart_base64}"}}
                    ]
                }
            ],
            model="llama-3.2-90b-vision-preview",
            temperature=0.3,
            max_tokens=300
        )
        print(f"✅ {symbol} AI tamamlandı")
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"❌ {symbol} AI hatası: {e}")
        return f"AI hatası: {str(e)[:100]}"

def main():
    print(f"🚀 Bot başlatıldı - {datetime.now()}")
    
    for i, symbol in enumerate(WATCHLIST):
        try:
            if i > 0:
                time.sleep(2)
            
            df = fetch_stock_data(symbol)
            chart_buf, chart_base64 = create_chart(symbol, df)
            signals = generate_signals(df)
            ai_analysis = analyze_with_ai(symbol, df, signals, chart_base64)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            change = ((latest['Close'] / prev['Close'] - 1) * 100)
            
            text = f"""
━━━━━━━━━━━━━━━━━━━━
*{symbol}*
💵 ${latest['Close']:.2f} ({change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━

🤖 *AI ANALİZ:*
{ai_analysis}

📈 *SİNYALLER:*
{chr(10).join('• ' + s for s in signals)}
"""
            
            bot.send_photo(TELEGRAM_CHAT_ID, chart_buf)
            bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode='Markdown')
            print(f"✅ {symbol} gönderildi")
            
        except Exception as e:
            print(f"❌ {symbol}: {e}")
            bot.send_message(TELEGRAM_CHAT_ID, f"❌ *{symbol}*: Hata", parse_mode='Markdown')
    
    print("🏁 Tamamlandı")

if __name__ == '__main__':
    main()
