import requests
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from groq import Groq
import telebot
import os
from datetime import datetime, timedelta
import time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import base64

WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

def fetch_stock_data(symbol):
    """Polygon (Massive) API ile gerçek veri çek"""
    print(f"📥 {symbol} verisi çekiliyor...")
    
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        url = f'https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date.strftime("%Y-%m-%d")}/{end_date.strftime("%Y-%m-%d")}?apiKey={POLYGON_API_KEY}'
        
        response = requests.get(url, timeout=15)
        data = response.json()
        
        if data.get('status') != 'OK' or not data.get('results'):
            raise Exception(f"API hatası: {data.get('status', 'Veri yok')}")
        
        results = data['results']
        df = pd.DataFrame(results)
        df['date'] = pd.to_datetime(df['t'], unit='ms')
        df = df.set_index('date')
        df = df.rename(columns={'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        if len(df) < 50:
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

def create_chart(symbol, df):
    """Profesyonel grafik oluştur"""
    print(f"📊 {symbol} için grafik oluşturuluyor...")
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    fig.patch.set_facecolor('#0e1117')
    
    # Fiyat grafiği
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
    ax2.axhline(y=70, color='#ff3b30', linestyle='--', alpha=0.5, linewidth=1)
    ax2.axhline(y=30, color='#34c759', linestyle='--', alpha=0.5, linewidth=1)
    ax2.fill_between(df.index, df['RSI'], 50, where=(df['RSI'] >= 50), alpha=0.3, color='#34c759')
    ax2.fill_between(df.index, df['RSI'], 50, where=(df['RSI'] < 50), alpha=0.3, color='#ff3b30')
    ax2.set_ylabel('RSI', color='white', fontsize=12)
    ax2.tick_params(colors='white')
    ax2.set_ylim([0, 100])
    ax2.grid(True, alpha=0.1, color='white')
    
    # Hacim
    ax3.set_facecolor('#1a1d24')
    colors = ['#34c759' if close >= open_ else '#ff3b30' for close, open_ in zip(df['Close'], df['Open'])]
    ax3.bar(df.index, df['Volume'], color=colors, alpha=0.5, width=0.8)
    ax3.set_ylabel('Hacim', color='white', fontsize=12)
    ax3.tick_params(colors='white')
    ax3.grid(True, alpha=0.1, color='white')
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    
    plt.tight_layout()
    
    # BytesIO'ya kaydet
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor='#0e1117', edgecolor='none')
    buf.seek(0)
    plt.close()
    
    # Base64'e çevir (AI için)
    img_base64 = base64.b64encode(buf.getvalue()).decode()
    buf.seek(0)
    
    print(f"✅ {symbol} grafik hazır")
    return buf, img_base64

def generate_signals(df):
    """Teknik sinyaller"""
    latest = df.iloc[-1]
    signals = []
    
    if pd.notna(latest['RSI']):
        if latest['RSI'] < 30:
            signals.append(f"🟢 RSI: {latest['RSI']:.1f} (Aşırı satım)")
        elif latest['RSI'] > 70:
            signals.append(f"🔴 RSI: {latest['RSI']:.1f} (Aşırı alım)")
        else:
            signals.append(f"⚪ RSI: {latest['RSI']:.1f} (Nötr)")
    
    if pd.notna(latest['SMA_50']) and pd.notna(latest['SMA_20']):
        if latest['Close'] > latest['SMA_50'] and latest['Close'] > latest['SMA_20']:
            signals.append("📈 Güçlü yükseliş trendi")
        elif latest['Close'] > latest['SMA_50']:
            signals.append("📊 Yükseliş trendi")
        else:
            signals.append("📉 Düşüş eğilimi")
    
    avg_volume = df['Volume'].tail(20).mean()
    volume_ratio = latest['Volume'] / avg_volume
    if volume_ratio > 1.5:
        signals.append(f"🔊 Yüksek hacim: {volume_ratio:.1f}x")
    
    return signals

def analyze_with_ai(symbol, df, signals, chart_base64):
    """AI analizi - GRAFİK GÖRÜYOR!"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change = ((latest['Close'] / prev['Close'] - 1) * 100)
    
    week_ago = df.iloc[-7] if len(df) >= 7 else prev
    week_change = ((latest['Close'] / week_ago['Close'] - 1) * 100)
    
    prompt = f"""Sen profesyonel bir teknik analiz uzmanısın. Yukarıdaki GRAFİĞİ İNCELE ve aşağıdaki verilerle birlikte analiz yap:

Hisse: {symbol}
Güncel Fiyat: ${latest['Close']:.2f}
Günlük Değişim: {change:+.2f}%
Haftalık Değişim: {week_change:+.2f}%
RSI (14): {latest['RSI']:.1f}
20 Günlük Ortalama: ${latest['SMA_20']:.2f}
50 Günlük Ortalama: ${latest['SMA_50']:.2f}

Teknik Sinyaller: {', '.join(signals)}

GRAFİKTE NE GÖRÜYORSUN?
- Trend çizgileri var mı?
- Destek/direnç seviyeleri nerede?
- Formasyon var mı? (üçgen, baş-omuz, vb.)
- Hacim ile fiyat uyumlu mu?

SADECE şu formatta yaz (max 100 kelime):

📊 GRAFİK ANALİZİ: [grafikte gördüklerini açıkla]
💡 ÖNERİ: AL/TUT/SAT [sebep]
⚠️ RİSK: Düşük/Orta/Yüksek [neden]
🎯 HEDEFLER: [destek ve direnç seviyeleri]"""

    try:
        print(f"🤖 {symbol} AI analizi yapılıyor (grafik ile)...")
        response = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{chart_base64}"}
                        }
                    ]
                }
            ],
            model="llama-3.2-90b-vision-preview",
            temperature=0.3,
            max_tokens=300
        )
        ai_text = response.choices[0].message.content
        print(f"✅ {symbol} AI analizi tamamlandı (grafik incelendi)")
        return ai_text
        
    except Exception as e:
        print(f"❌ {symbol} AI hatası: {e}")
        return "AI analizi yapılamadı"

def create_report(symbol, df):
    """Tam rapor + grafik"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    change = ((latest['Close'] / prev['Close'] - 1) * 100)
    
    # Grafik oluştur
    chart_buf, chart_base64 = create_chart(symbol, df)
    
    # Sinyaller
    signals = generate_signals(df)
    
    # AI analizi (grafik ile!)
    ai_analysis = analyze_with_ai(symbol, df, signals, chart_base64)
    
    text_report = f"""
━━━━━━━━━━━━━━━━━━━━
*{symbol}*
💵 ${latest['Close']:.2f} ({change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━

🤖 *AI ANALİZ (GRAFİK İNCELENDİ):*
{ai_analysis}

📈 *TEKNİK SİNYALLER:*
{chr(10).join('• ' + s for s in signals)}
"""
    
    return text_report, chart_buf

def main():
    """Ana fonksiyon"""
    print(f"🚀 Bot başlatıldı - {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    all_reports = []
    
    for i, symbol in enumerate(WATCHLIST):
        try:
            if i > 0:
                time.sleep(3)  # Rate limit
            
            df = fetch_stock_data(symbol)
            text_report, chart_image = create_report(symbol, df)
            
            # Önce grafik, sonra metin gönder
            bot.send_photo(TELEGRAM_CHAT_ID, chart_image)
            bot.send_message(TELEGRAM_CHAT_ID, text_report, parse_mode='Markdown')
            
            print(f"✅ {symbol} tamamlandı (grafik + analiz gönderildi)")
            
        except Exception as e:
            print(f"❌ {symbol} başarısız: {e}")
            bot.send_message(TELEGRAM_CHAT_ID, f"❌ *{symbol}*: Analiz yapılamadı", parse_mode='Markdown')
    
    print(f"🏁 Tamamlandı - {len(WATCHLIST)} hisse analiz edildi")

if __name__ == '__main__':
    main()
