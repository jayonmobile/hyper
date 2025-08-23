from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import ccxt
import talib
import numpy as np
import time
from datetime import datetime
import pytz
import json
from hyperliquid.info import Info
from hyperliquid.utils import constants
import example_utils
import threading


import asyncio

import pytest

from async_hyperliquid.async_hyper import AsyncHyper
from async_hyperliquid.utils.types import Cloid, LimitOrder
from typing import AsyncGenerator
import pytest_asyncio



app = Flask(__name__)
socketio = SocketIO(app)



@pytest_asyncio.fixture(loop_scope="session")
async def hl() -> AsyncGenerator[AsyncHyper, None]:
    address = "0x7605904Da82A2ea6Bc7676f6206DD1157f82D519"
    api_key = "0xfb01464b3ed0ef6c22b5fe9950f13eb78dd4f61a33ab020cb4c1159c2a7e70cf"
    is_mainnet = True
    hl = AsyncHyper(address, api_key, is_mainnet)
    try:
        await hl.init_metas()
        yield hl
    finally:
        await hl.close()


dex = ccxt.hyperliquid({
    "walletAddress": "0x7605904Da82A2ea6Bc7676f6206DD1157f82D519", # /!\ Adresse publique de votre compte
    "privateKey": "0xfb01464b3ed0ef6c22b5fe9950f13eb78dd4f61a33ab020cb4c1159c2a7e70cf",    # Clé privée de la clé API
})

address, info, exchange = example_utils.setup(base_url=constants.MAINNET_API_URL, skip_ws=True)



def get_recent_prices(exchange, symbol, timeframe, limit):
    """
    Fetch recent OHLCV data and extract closing prices.
    """
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    return ohlcv


@app.route('/')
def index():
    info = Info(constants.TESTNET_API_URL, skip_ws=True)
    user_state = info.user_state("0x7605904Da82A2ea6Bc7676f6206DD1157f82D519")
    print(user_state)
    return render_template('index.html')


@app.route('/ajax_sample', methods=['GET','POST'])
def ajax_sample():
    if request.method == "POST":
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        output = firstname + lastname
        if firstname and lastname:
            return jsonify({'output':'Your Name is ' + output + ', right?'})
        return jsonify({'error' : 'Missing data!'})


@app.route('/check_position', methods=['GET','POST'])
def check_position():
    if request.method == "POST":
        #address, info, exchange = example_utils.setup(base_url=constants.TESTNET_API_URL, skip_ws=True)

        # Get the user state and print out position information
        output = dex.fetch_balance()
        

        return jsonify({'output' : 'Position!' + str(output)})



# Open Order
order_result = None
# 直接在函数内部初始化 AsyncHyper 实例
address = "0x7605904Da82A2ea6Bc7676f6206DD1157f82D519"
api_key = "0xfb01464b3ed0ef6c22b5fe9950f13eb78dd4f61a33ab020cb4c1159c2a7e70cf"
is_mainnet = True

@app.route('/open_order_buy', methods=['GET','POST'])
async def open_order_buy():
    hl = AsyncHyper(address, api_key, is_mainnet)
    try:
        await hl.init_metas()
        
        # 以下是原有的订单逻辑
        coin = "SOL"
        is_buy = True
        sz = 0.01
        px = 250 #g_close_price
        tp_px = px + 0.20
        sl_px = px - 1
        o1 = {
            "coin": coin,
            "is_buy": is_buy,
            "sz": sz,
            "px": px,
            "ro": False,
            "order_type": LimitOrder.ALO.value,
        }
        # 止盈订单
        tp_order_type = {
            "trigger": {"isMarket": False, "triggerPx": tp_px, "tpsl": "tp"}
        }
        o2 = {
            "coin": coin,
            "is_buy": not is_buy,
            "sz": sz,
            "px": px,
            "ro": True,
            "order_type": tp_order_type,
        }
        # 止损订单
        sl_order_type = {
            "trigger": {"isMarket": False, "triggerPx": sl_px, "tpsl": "sl"}
        }
        o3 = {
            "coin": coin,
            "is_buy": not is_buy,
            "sz": sz,
            "px": px,
            "ro": True,
            "order_type": sl_order_type,
        }

        resp = await hl.batch_place_orders([o1], is_market=True)  # type: ignore
        print("\nBatch place market orders response: ", resp)
        assert resp["status"] == "ok"

        orders = [o2, o3]
        resp = await hl.batch_place_orders(orders, grouping="positionTpsl")  # type: ignore
        print("Batch place orders with 'positionTpsl' response: ", resp)
        assert resp["status"] == "ok"

        # 注释掉关闭所有仓位的代码，避免刚开单就平仓
        # resp = await hl.close_all_positions()
        # print("Close all positions response: ", resp)
        # assert resp["status"] == "ok"

        orders = [o1, o2, o3]
        resp = await hl.batch_place_orders(orders, grouping="normalTpsl")  # type: ignore
        print("Batch place orders with 'normalTpsl' response: ", resp)

        orders = await hl.get_user_open_orders(is_frontend=True)
        cancels = []
        for o in orders:
            coin = o["coin"]
            oid = o["oid"]
            cancels.append((coin, oid))
        resp = await hl.batch_cancel_orders(cancels)
        print("Batch cancel orders response: ", resp)
        assert resp["status"] == "ok"

        return jsonify({'output': 'Open BUY Order! '})
    finally:
        await hl.close()  # 确保资源正确释放


@app.route('/open_order_sell', methods=['GET','POST'])
async def open_order_sell():
    hl = AsyncHyper(address, api_key, is_mainnet)
    try:
        await hl.init_metas()
        
        # 以下是原有的订单逻辑
        coin = "SOL"
        is_buy = True
        sz = 0.01
        px = 250 #g_close_price
        tp_px = px - 0.20
        sl_px = px + 1
        o1 = {
            "coin": coin,
            "is_buy": not is_buy,
            "sz": sz,
            "px": px,
            "ro": False,
            "order_type": LimitOrder.ALO.value,
        }
        # 止盈订单
        tp_order_type = {
            "trigger": {"isMarket": False, "triggerPx": tp_px, "tpsl": "tp"}
        }
        o2 = {
            "coin": coin,
            "is_buy": is_buy,
            "sz": sz,
            "px": px,
            "ro": True,
            "order_type": tp_order_type,
        }
        # 止损订单
        sl_order_type = {
            "trigger": {"isMarket": False, "triggerPx": sl_px, "tpsl": "sl"}
        }
        o3 = {
            "coin": coin,
            "is_buy": is_buy,
            "sz": sz,
            "px": px,
            "ro": True,
            "order_type": sl_order_type,
        }

        resp = await hl.batch_place_orders([o1], is_market=True)  # type: ignore
        print("\nBatch place market orders response: ", resp)
        assert resp["status"] == "ok"

        orders = [o2, o3]
        resp = await hl.batch_place_orders(orders, grouping="positionTpsl")  # type: ignore
        print("Batch place orders with 'positionTpsl' response: ", resp)
        assert resp["status"] == "ok"

        # 注释掉关闭所有仓位的代码，避免刚开单就平仓
        # resp = await hl.close_all_positions()
        # print("Close all positions response: ", resp)
        # assert resp["status"] == "ok"

        orders = [o1, o2, o3]
        resp = await hl.batch_place_orders(orders, grouping="normalTpsl")  # type: ignore
        print("Batch place orders with 'normalTpsl' response: ", resp)

        orders = await hl.get_user_open_orders(is_frontend=True)
        cancels = []
        for o in orders:
            coin = o["coin"]
            oid = o["oid"]
            cancels.append((coin, oid))
        resp = await hl.batch_cancel_orders(cancels)
        print("Batch cancel orders response: ", resp)
        assert resp["status"] == "ok"

        return jsonify({'output': 'Open SELL Order! '})
    finally:
        await hl.close()  # 确保资源正确释放




@app.route('/cancel_order', methods=['GET','POST'])
def cancel_order():
    return jsonify({'output' : 'Cancel Order! '})























g_close_price = 0
def background_task():
    global g_close_price
    

    exchange = ccxt.hyperliquid()
    symbol = 'SOL/USDC:USDC'
    timeframes = ['1m', '5m', '15m']
    limit = 1000

    while True:
        try:
            all_data = {}
            for timeframe in timeframes:
                print('ccccccccccc = '+str(g_close_price))

                ohlcv = get_recent_prices(exchange, symbol, timeframe, limit)
                closes = [float(candle[4]) for candle in ohlcv]


                data = []
                for i, candle in enumerate(ohlcv):
                    timestamp, open_price, high_price, low_price, close_price, volume = candle
                    # Keep the timestamp as is (in milliseconds, as fetched from ccxt)
                    # No need to convert to Hong Kong time string anymore
                    g_close_price = close_price



                    data_point = {
                        'time': timestamp,  # Now it's the Unix timestamp in milliseconds
                        'open': None if np.isnan(open_price) else float(open_price),
                        'high': None if np.isnan(high_price) else float(high_price),
                        'low': None if np.isnan(low_price) else float(low_price),
                        'close': None if np.isnan(close_price) else float(close_price),
                        'volume': None if np.isnan(volume) else float(volume),

                    }
                    data.append(data_point)

                all_data[timeframe] = data

            socketio.emit('ohlcv_update', all_data)
            time.sleep(1)  # Wait for 1 minute (60 seconds) before the next update
        except Exception as e:
            print(f"Error in background task: {str(e)}")
            time.sleep(1)  # Wait for 1 minute (60 seconds) before retrying














if __name__ == "__main__":
    threading.Thread(target=background_task, daemon=True).start()
    socketio.run(app, debug=True)