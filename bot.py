import os
import json
import time
import random
import asyncio
import pytz
from datetime import datetime

# --- Library Pihak Ketiga ---
from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account
from aiohttp import ClientSession, ClientTimeout, ClientResponseError
from fake_useragent import FakeUserAgent
from colorama import Fore, Style, init
from dotenv import load_dotenv

# Inisialisasi Colorama dan Dotenv
init(autoreset=True)
load_dotenv()

# Zona Waktu
wib = pytz.timezone('Asia/Jakarta')

### --- KONFIGURASI --- ###
# Ubah semua pengaturan Anda di sini jika perlu.
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
RPC_URL = os.getenv("RPC_URL", "https://testnet.dplabs-internal.com")

# Pengaturan Jumlah Aksi
JUMLAH_SWAP = 8
JUMLAH_TAMBAH_LP = 5 # Atur ke 0 jika tidak ingin menambah LP

# Pengaturan Nominal untuk setiap Aksi
SWAP_AMOUNTS = {
    "PHRS": 0.001, "WPHRS": 0.001, "USDC": 0.01,
    "USDT": 0.01, "WETH": 0.00001, "WBTC": 0.000001,
}
ADD_LP_AMOUNTS = {
    "WPHRS": 0.001, "USDC": 0.01, "USDT": 0.01,
    "WETH": 0.00001, "WBTC": 0.000001,
}

# Pengaturan Jeda Waktu (Delay) antar transaksi dalam detik
JEDA_MINIMUM = 30
JEDA_MAKSIMUM = 70
### --- AKHIR KONFIGURASI --- ###


class Faroswap:
    def __init__(self, rpc_url: str) -> None:
        self.HEADERS = { "Accept": "application/json, text/plain, */*", "Origin": "https://faroswap.xyz", "Referer": "https://faroswap.xyz/", "User-Agent": FakeUserAgent().random }
        self.chain_id = 688688
        
        # Alamat Kontrak
        self.PHRS_CONTRACT_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        self.WPHRS_CONTRACT_ADDRESS = "0x3019B247381c850ab53Dc0EE53bCe7A07Ea9155f"
        self.USDC_CONTRACT_ADDRESS = "0x72df0bcd7276f2dFbAc900D1CE63c272C4BCcCED"
        self.USDT_CONTRACT_ADDRESS = "0xD4071393f8716661958F766DF660033b3d35fD29"
        self.WETH_CONTRACT_ADDRESS = "0x4E28826d32F1C398DED160DC16Ac6873357d048f"
        self.WBTC_CONTRACT_ADDRESS = "0x8275c526d1bCEc59a31d673929d3cE8d108fF5c7"
        self.MIXSWAP_ROUTER_ADDRESS = "0x3541423f25A1Ca5C98fdBCf478405d3f0aaD1164"
        self.POOL_ROUTER_ADDRESS = "0xf05Af5E9dC3b1dd3ad0C087BD80D7391283775e0"
        
        self.tickers = ["WPHRS", "USDC", "USDT", "WETH", "WBTC"]
        self.ERC20_CONTRACT_ABI = json.loads('''[{"type":"function","name":"balanceOf","stateMutability":"view","inputs":[{"name":"address","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},{"type":"function","name":"allowance","stateMutability":"view","inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},{"type":"function","name":"approve","stateMutability":"nonpayable","inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},{"type":"function","name":"decimals","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint8"}]}]''')
        self.UNISWAP_V2_ABI = json.loads('''[{"type":"function","name":"getAmountsOut","stateMutability":"view","inputs":[{"name":"amountIn","type":"uint256"},{"name":"path","type":"address[]"},{"name":"fees","type":"uint256[]"}],"outputs":[{"name":"amounts","type":"uint256[]"}]},{"type":"function","name":"addLiquidity","stateMutability":"payable","inputs":[{"name":"tokenA","type":"address"},{"name":"tokenB","type":"address"},{"name":"fee","type":"uint256"},{"name":"amountADesired","type":"uint256"},{"name":"amountBDesired","type":"uint256"},{"name":"amountAMin","type":"uint256"},{"name":"amountBMin","type":"uint256"},{"name":"to","type":"address"},{"name":"deadline","type":"uint256"}],"outputs":[{"name":"amountA","type":"uint256"},{"name":"amountB","type":"uint256"},{"name":"liquidity","type":"uint256"}]}]''')
        
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self.pool_contract = self.web3.eth.contract(address=Web3.to_checksum_address(self.POOL_ROUTER_ADDRESS), abi=self.UNISWAP_V2_ABI)

    def log(self, message):
        timestamp = datetime.now(wib).strftime('%H:%M:%S')
        print(f"{Style.BRIGHT}{Fore.CYAN}[{timestamp}]{Style.RESET_ALL} | {message}")

    async def get_token_balance(self, address: str, contract_address: str):
        # ... (fungsi ini tidak berubah) ...
        try:
            if contract_address == self.PHRS_CONTRACT_ADDRESS:
                balance = self.web3.eth.get_balance(address)
                return self.web3.from_wei(balance, 'ether')
            else:
                token_contract = self.web3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=self.ERC20_CONTRACT_ABI)
                balance = await asyncio.to_thread(token_contract.functions.balanceOf(address).call)
                decimals = await asyncio.to_thread(token_contract.functions.decimals().call)
                return balance / (10 ** decimals)
        except Exception as e:
            self.log(f"{Fore.RED}Gagal mendapatkan saldo token: {e}")
            return 0
            
    async def wait_for_receipt(self, tx_hash):
        # ... (fungsi ini tidak berubah) ...
        for i in range(10):
            try:
                receipt = await asyncio.to_thread(self.web3.eth.wait_for_transaction_receipt, tx_hash, timeout=60)
                self.log(f"{Fore.GREEN}Transaksi sukses! Block: {receipt.blockNumber}")
                self.log(f"Explorer: https://testnet.pharosscan.xyz/tx/{tx_hash.hex()}")
                return receipt
            except (Exception, TransactionNotFound):
                self.log(f"{Fore.YELLOW}Menunggu receipt... ({i+1}/10)")
                await asyncio.sleep(15)
        self.log(f"{Fore.RED}Gagal mendapatkan receipt transaksi setelah beberapa kali percobaan.")
        return None

    async def approve_token(self, account, spender_address, token_address, amount_wei):
        # ... (fungsi ini tidak berubah) ...
        address = account.address
        token_contract = self.web3.eth.contract(address=Web3.to_checksum_address(token_address), abi=self.ERC20_CONTRACT_ABI)
        
        allowance = await asyncio.to_thread(token_contract.functions.allowance(address, Web3.to_checksum_address(spender_address)).call)
        if allowance >= amount_wei:
            self.log(f"{Fore.GREEN}Allowance sudah cukup, tidak perlu approve.")
            return True

        self.log(f"Memerlukan approval untuk token {token_address}...")
        approve_tx_data = token_contract.functions.approve(Web3.to_checksum_address(spender_address), 2**256 - 1)
        
        tx_params = {
            'from': address,
            'gasPrice': self.web3.to_wei('1', 'gwei'),
            'nonce': self.web3.eth.get_transaction_count(address),
            'chainId': self.chain_id
        }
        tx_params['gas'] = await asyncio.to_thread(approve_tx_data.estimate_gas, tx_params)
        
        approve_tx = await asyncio.to_thread(approve_tx_data.build_transaction, tx_params)
        signed_tx = account.sign_transaction(approve_tx)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        receipt = await self.wait_for_receipt(tx_hash)
        return receipt is not None

    async def get_dodo_route(self, from_token, to_token, amount_wei, user_address):
        # ... (fungsi ini tidak berubah) ...
        url = (f"https://api.dodoex.io/route-service/v2/widget/getdodoroute?chainId={self.chain_id}&deadLine={int(time.time()) + 300}&apikey=a37546505892e1a952&slippage=1&fromTokenAddress={from_token}&toTokenAddress={to_token}&fromAmount={amount_wei}&userAddr={user_address}&estimateGas=true")
        try:
            async with ClientSession(timeout=ClientTimeout(total=30)) as session:
                async with session.get(url=url, headers=self.HEADERS) as response:
                    response.raise_for_status()
                    result = await response.json()
                    if result.get("status") == 200: return result.get("data")
                    else: self.log(f"{Fore.RED}DODO API Error: {result.get('data', 'Tidak ada rute')}"); return None
        except Exception as e: self.log(f"{Fore.RED}Gagal mendapatkan rute dari DODOEX: {e}"); return None

    async def perform_swap(self, account, from_ticker, to_ticker, amount_decimal):
        # ... (fungsi ini tidak berubah) ...
        address = account.address
        def get_contract(ticker): return getattr(self, f"{ticker}_CONTRACT_ADDRESS") if ticker != "PHRS" else self.PHRS_CONTRACT_ADDRESS
        from_token_address = get_contract(from_ticker); to_token_address = get_contract(to_ticker)
        balance = await self.get_token_balance(address, from_token_address)
        if balance < amount_decimal: self.log(f"{Fore.RED}Saldo {from_ticker} tidak cukup. Saldo: {balance}, butuh: {amount_decimal}"); return False
        if from_token_address == self.PHRS_CONTRACT_ADDRESS: decimals = 18
        else:
            token_contract = self.web3.eth.contract(address=Web3.to_checksum_address(from_token_address), abi=self.ERC20_CONTRACT_ABI)
            decimals = await asyncio.to_thread(token_contract.functions.decimals().call)
        amount_wei = int(amount_decimal * (10**decimals))
        self.log(f"Memulai swap: {amount_decimal} {from_ticker} -> {to_ticker}")
        route_data = await self.get_dodo_route(from_token_address, to_token_address, amount_wei, address)
        if not route_data: return False
        if from_token_address != self.PHRS_CONTRACT_ADDRESS:
            approved = await self.approve_token(account, route_data['to'], from_token_address, amount_wei)
            if not approved: self.log(f"{Fore.RED}Gagal approve token, swap dibatalkan."); return False
        swap_tx = {'to': Web3.to_checksum_address(route_data['to']), 'from': address, 'value': int(route_data.get('value', 0)), 'data': route_data['data'], 'gasPrice': self.web3.to_wei('1', 'gwei'), 'nonce': self.web3.eth.get_transaction_count(address), 'chainId': self.chain_id}
        try: swap_tx['gas'] = await asyncio.to_thread(self.web3.eth.estimate_gas, swap_tx)
        except Exception as e: self.log(f"{Fore.YELLOW}Gagal estimasi gas, menggunakan gas limit dari DODO. Error: {e}"); swap_tx['gas'] = int(route_data.get('gasLimit', 500000))
        signed_tx = account.sign_transaction(swap_tx)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await self.wait_for_receipt(tx_hash)
        return receipt is not None

    async def perform_add_liquidity(self, account, token_a_ticker, token_b_ticker, amount_a_decimal):
        address = account.address
        self.log(f"Memulai Tambah Likuiditas: {amount_a_decimal} {token_a_ticker} dengan {token_b_ticker}")

        def get_contract(ticker): return getattr(self, f"{ticker}_CONTRACT_ADDRESS")
        token_a_address = get_contract(token_a_ticker)
        token_b_address = get_contract(token_b_ticker)
        
        # Cek Saldo Token A
        balance_a = await self.get_token_balance(address, token_a_address)
        if balance_a < amount_a_decimal: self.log(f"{Fore.RED}Saldo {token_a_ticker} tidak cukup. Saldo: {balance_a}, butuh: {amount_a_decimal}"); return False

        # Dapatkan Desimal dan konversi ke wei
        token_a_contract = self.web3.eth.contract(address=Web3.to_checksum_address(token_a_address), abi=self.ERC20_CONTRACT_ABI)
        decimals_a = await asyncio.to_thread(token_a_contract.functions.decimals().call)
        amount_a_wei = int(amount_a_decimal * (10**decimals_a))

        # Dapatkan jumlah token B yang dibutuhkan
        try:
            amounts_out = await asyncio.to_thread(self.pool_contract.functions.getAmountsOut(amount_a_wei, [token_a_address, token_b_address], [30]).call)
            amount_b_wei = amounts_out[1]
        except Exception as e: self.log(f"{Fore.RED}Gagal menghitung jumlah token B: {e}"); return False

        # Approve kedua token
        self.log(f"Approval untuk {token_a_ticker}...")
        if not await self.approve_token(account, self.POOL_ROUTER_ADDRESS, token_a_address, amount_a_wei): return False
        
        self.log(f"Approval untuk {token_b_ticker}...")
        if not await self.approve_token(account, self.POOL_ROUTER_ADDRESS, token_b_address, amount_b_wei): return False
        
        # Bangun transaksi addLiquidity
        deadline = int(time.time()) + 600
        slippage = 0.01 # 1% slippage
        
        add_lp_data = self.pool_contract.functions.addLiquidity(
            Web3.to_checksum_address(token_a_address),
            Web3.to_checksum_address(token_b_address),
            30,
            amount_a_wei,
            amount_b_wei,
            int(amount_a_wei * (1 - slippage)),
            int(amount_b_wei * (1 - slippage)),
            address,
            deadline
        )
        
        tx_params = { 'from': address, 'gasPrice': self.web3.to_wei('1', 'gwei'), 'nonce': self.web3.eth.get_transaction_count(address), 'chainId': self.chain_id }
        try: tx_params['gas'] = await asyncio.to_thread(add_lp_data.estimate_gas, tx_params)
        except Exception as e: self.log(f"{Fore.YELLOW}Gagal estimasi gas, menggunakan nilai default. Error: {e}"); tx_params['gas'] = 500000
        
        tx = await asyncio.to_thread(add_lp_data.build_transaction, tx_params)
        signed_tx = account.sign_transaction(tx)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await self.wait_for_receipt(tx_hash)
        return receipt is not None

    async def run(self):
        # ... (Fungsi `run` diperbarui untuk memanggil fase LP) ...
        if not PRIVATE_KEY: self.log(f"{Fore.RED}Error: PRIVATE_KEY tidak ditemukan di file .env."); return

        account = Account.from_key(PRIVATE_KEY)
        address = account.address
        self.log(f"{Style.BRIGHT}Memulai bot untuk akun: {address}")
        self.log(f"{Style.BRIGHT}Menggunakan RPC: {self.web3.provider.endpoint_uri}")

        # FASE 1: SWAP
        if JUMLAH_SWAP > 0:
            self.log(f"{Style.BRIGHT}\n--- Memulai Fase Swap ({JUMLAH_SWAP} kali) ---")
            # ... (Logika swap tidak berubah) ...
            for i in range(JUMLAH_SWAP):
                self.log(f"{Style.BRIGHT}--- Swap #{i + 1}/{JUMLAH_SWAP} ---")
                from_ticker, to_ticker = "", ""
                if i == 0:
                    self.log(f"{Fore.YELLOW}Info: Swap pertama, memaksa jual PHRS untuk mendapatkan token lain.")
                    from_ticker, to_ticker = "PHRS", random.choice(self.tickers)
                else:
                    self.log("Info: Mencari token dengan saldo yang cukup untuk di-swap...")
                    eligible_tickers = []
                    all_possible_tickers = ["PHRS"] + self.tickers
                    for ticker in all_possible_tickers:
                        contract_address = getattr(self, f"{ticker}_CONTRACT_ADDRESS", self.PHRS_CONTRACT_ADDRESS)
                        balance = await self.get_token_balance(address, contract_address)
                        if balance > SWAP_AMOUNTS.get(ticker, 0): eligible_tickers.append(ticker)
                    if not eligible_tickers: self.log(f"{Fore.RED}Tidak ada token dengan saldo yang cukup untuk di-swap."); break
                    from_ticker = random.choice(eligible_tickers)
                    temp_tickers = self.tickers + ["PHRS"]
                    to_ticker = random.choice(temp_tickers)
                    while from_ticker == to_ticker: to_ticker = random.choice(temp_tickers)
                self.log(f"Dipilih pasangan: {from_ticker} -> {to_ticker}")
                await self.perform_swap(account, from_ticker, to_ticker, SWAP_AMOUNTS.get(from_ticker, 0.001))
                if i < JUMLAH_SWAP - 1:
                    delay = random.randint(JEDA_MINIMUM, JEDA_MAKSIMUM)
                    self.log(f"Menunggu {delay} detik sebelum transaksi berikutnya...")
                    await asyncio.sleep(delay)
        
        # FASE 2: TAMBAH LIKUIDITAS (LP)
        if JUMLAH_TAMBAH_LP > 0:
            self.log(f"{Style.BRIGHT}\n--- Memulai Fase Tambah Likuiditas ({JUMLAH_TAMBAH_LP} kali) ---")
            for i in range(JUMLAH_TAMBAH_LP):
                self.log(f"{Style.BRIGHT}--- Tambah LP #{i + 1}/{JUMLAH_TAMBAH_LP} ---")
                
                # Pilih pasangan acak dari token yang tersedia (tidak termasuk PHRS native)
                token_a = random.choice(self.tickers)
                token_b = random.choice(self.tickers)
                while token_a == token_b:
                    token_b = random.choice(self.tickers)
                
                amount = ADD_LP_AMOUNTS.get(token_a, 0.001)
                
                await self.perform_add_liquidity(account, token_a, token_b, amount)
                
                if i < JUMLAH_TAMBAH_LP - 1:
                    delay = random.randint(JEDA_MINIMUM, JEDA_MAKSIMUM)
                    self.log(f"Menunggu {delay} detik sebelum transaksi berikutnya...")
                    await asyncio.sleep(delay)

        self.log(f"{Style.BRIGHT}{Fore.GREEN}\nSemua tugas telah selesai untuk akun {address}.")

async def main():
    try:
        bot = Faroswap(rpc_url=RPC_URL)
        await bot.run()
    except Exception as e:
        print(f"\n{Fore.RED}Terjadi kesalahan fatal: {e}")

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print(f"\n{Fore.YELLOW}Bot dihentikan oleh pengguna.")
