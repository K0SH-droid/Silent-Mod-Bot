from flask import Flask
import os

app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))  # << das ist wichtig für Render
    app.run(host='0.0.0.0', port=port)
