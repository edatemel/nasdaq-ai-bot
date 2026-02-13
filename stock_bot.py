- name: Run bot
        env:
          TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
        run: python stock_bot.py
