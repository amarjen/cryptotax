#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import csv
import logging
import decimal
import argparse
import itertools
from decimal import Decimal
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any, Union

decimal.getcontext().prec = 8
logger = logging.getLogger(__name__)


class Transaction:
    def __init__(
        self,
        txid: str,
        date: datetime,
        tx_type: str,
        qty1: Decimal,
        asset1: str,
        qty2: Decimal,
        asset2: str,
    ):
        self.txid = txid
        self.date = date
        self.type = tx_type
        self.qty1 = qty1
        self.asset1 = asset1
        self.qty2 = qty2
        self.asset2 = asset2

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        return cls(
            txid=data["txid"],
            date=datetime.strptime(data["date"], "%d/%m/%Y"),
            tx_type=data["type"],
            qty1=Decimal(data["qty1"]),
            asset1=data["asset1"],
            qty2=Decimal(data["qty2"]),
            asset2=data["asset2"],
        )

    def __repr__(self):
        return (
            f"Transaction(txid={self.txid}, date={self.date}, type={self.type}, qty1={self.qty1}, "
            f"asset1={self.asset1}, qty2={self.qty2}, asset2={self.asset2})"
        )


class Lot:
    def __init__(self, date: datetime, asset: str, qty: Decimal, cost: Decimal):
        self.date = date
        self.asset = asset
        self.qty = qty
        self.cost = cost

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Lot":
        return cls(
            date=data["date"],
            asset=data["asset"],
            qty=data["qty"],
            cost=data["cost"],
        )

    def __repr__(self):
        return f"Lot(asset={self.asset}, date={self.date}, qty={self.qty}, cost={self.cost})"


class LotBasket:
    """
    Representa una canasta de lotes de un mismo activo.
    """

    def __init__(self, asset: str, lots: List[Lot] = None):
        self.asset = asset
        self.lots = lots if lots else list()

    def add_lot(self, lot: Lot):
        """Agrega un lote a la canasta."""
        if lot.asset != self.asset:
            raise ValueError(
                f"El activo del lote {lot.asset} debe ser el mismo que el de la canasta: {self.asset}"
            )

        self.lots.append(lot)

    @property
    def total_qty(self) -> Decimal:
        """
        Devuelve la cantidad total
        """
        return sum(lot.qty for lot in self.lots)

    @property
    def total_cost(self) -> Decimal:
        """
        Devuelve el coste total
        """
        return sum(lot.cost * lot.qty for lot in self.lots)

    @property
    def avg_cost(self) -> Decimal:
        """
        Devuelve el coste medio por unidad de activo
        """
        return self.total_cost / self.total_qty if self.total_qty else Decimal(0)

    def __repr__(self):
        return f"LotBasket(asset={self.asset}, lots={self.lots})"


class Inventory:
    def __init__(self, baskets: Dict[str, LotBasket] = None):
        self.baskets = baskets if baskets else {}

    def add_basket(self, basket: LotBasket):
        if basket.asset in self.baskets:
            self.baskets[basket.asset].lots.extend(basket.lots)
        else:
            self.baskets[basket.asset] = basket

    def add_lot(self, lot: Lot):
        if lot.asset not in self.baskets.keys():
            self.add_basket(LotBasket(asset=lot.asset))

        self.baskets[lot.asset].add_lot(lot)

    def total_qty(self, asset):
        return self.baskets[asset].total_qty

    @property
    def balance(self):
        return [
            {
                asset: {
                    "qty": self.baskets[asset].total_qty,
                    "basis": self.baskets[asset].avg_cost,
                }
            }
            for asset in self.baskets.keys()
        ]

    def print_balance(self):
        output = ""
        for asset in self.baskets.keys():
            basket = self.baskets[asset]
            output += (
                f"{asset}: ( {basket.total_qty:8.4f} @ {basket.avg_cost:.2f} EUR ) "
            )

        return output

    @staticmethod
    def from_csv(file_path):
        inventory = Inventory()
        with open(file_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # remove white spaces around keys and values
                row = {k.strip(): v.strip() for k, v in row.items()}
                try:
                    date = datetime.strptime(row["lot"].strip(), "%Y-%m-%d")
                    asset = row["asset"]
                    qty = Decimal(row["qty"])
                    avg_cost = Decimal(row["basis"])
                except ValueError as e:
                    logger.error(f"Error parsing CSV row: {row}. Exception: {e}")
                    continue

                # validate data
                if qty <= 0 or avg_cost <= 0:
                    logger.error(f"Invalid quantity or average cost in CSV row: {row}")
                    continue

                lot = Lot(date, asset, qty, avg_cost)
                inventory.add_lot(lot)
        return inventory

    def to_csv(self, file_path):
        with open(file_path, "w", newline="") as csvfile:
            fieldnames = ["lot", "asset", "qty", "basis"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for asset, basket in self.baskets.items():
                for lot in basket.lots:
                    writer.writerow(
                        {
                            "lot": lot.date.strftime("%Y-%m-%d"),
                            "asset": lot.asset,
                            "qty": f"{lot.qty:11.8f}",
                            "basis": f"{lot.cost:9.2f}",
                        }
                    )

    def __repr__(self):
        return f"Inventory(baskets={self.baskets})"


class TaxEngine:
    def __init__(
        self,
        year: int,
        criterio: str = "FIFO",
        initial_inventory: Inventory = None,
        transactions: List[Transaction] = None,
        base_asset: str = "EUR",
        btceur_file: str = None,
    ):
        self.year = year
        self.criterio = criterio
        self.inventory = initial_inventory or Inventory()
        self.transactions = transactions or []
        self.base_asset = base_asset
        self.tax_events = defaultdict(list)

        self.btceur = self._get_precio_btc(btceur_file)

    def read_transactions(self, files: List[str]):

        txs = []

        # Leer archivo de transacciones
        for transaction_file in files:
            try:
                with open(transaction_file, "r") as f:
                    txs.extend(list(csv.DictReader(f, delimiter=";")))
            except FileNotFoundError:
                print(f"Could not find transaction file: {transaction_file}")
                sys.exit(2)

        # asignar tipos de dato
        txs = [Transaction.from_dict(tx) for tx in txs]

        # ordenar por fecha
        self.transactions = sorted(txs, key=lambda tx: tx.date)

    def _init_transactions(self):
        """Prepara las transacciones antes de procesarlas"""
        # ordenar por fecha
        self.transactions = sorted(self.transactions, key=lambda tx: tx.date)

    def process_transactions(self):
        logger.info(f"INFORME DE TRANSACCIONES CON MONEDAS VIRTUALES - AÑO {self.year}")
        logger.info(f"Criterio de valoración: {self.criterio}")
        log_inventario_inicial = True

        handlers = {
            ("Buy", self.base_asset): self._handle_buy,
            ("Buy", "BTC"): self._handle_buy_permuta,
            ("Sell", self.base_asset): self._handle_sell,
            ("Sell", "BTC"): self._handle_sell_permuta,
        }

        self._init_transactions()
        for n, tx in enumerate(self.transactions):
            tx_current_year = tx.date.year == self.year

            assert tx.asset2 in ("BTC", "EUR")

            if tx_current_year and log_inventario_inicial:
                logger.info(f"Inventario inicial: {self.inventory.print_balance()}")
                log_inventario_inicial = False

            if tx.date.year <= self.year:
                handler = handlers.get((tx.type, tx.asset2))

                result = handler(tx)

                asset_to_pop = result["asset_to_pop"]
                qty_to_pop = result["qty_to_pop"]
                asset_to_push = result["asset_to_push"]
                qty_to_push = result["qty_to_push"]
                cost_basis = result["cost_basis"]
                income = result["income"]

                if tx_current_year:
                    logger.info(
                        f"\n*** TX {n:3}/{str(tx.date.year)[2:]} ******************************************************************"
                    )
                    logger.info(
                        f"{tx.date:%d-%m-%Y} {tx.type:4} {tx.asset1} {tx.qty1:8.4f} @ {cost_basis:8.2f} for {tx.asset2} {tx.qty2:8.2f}"
                    )

                if asset_to_pop:
                    assign_lot_basket = self.assign_lot(
                        asset_to_pop, qty_to_pop, log=tx_current_year
                    )

                if asset_to_push:
                    self.record_lot(tx.date, asset_to_push, qty_to_push, cost_basis)

                if tx_current_year:
                    if income:
                        self.record_tax_event(
                            tx.date, tx.asset1, income, assign_lot_basket
                        )

                    logger.info(f"       Inventario: {self.inventory.print_balance()}")

    def _handle_buy(self, tx):

        result = {
            "asset_to_pop": None,
            "qty_to_pop": None,
            "asset_to_push": tx.asset1,
            "qty_to_push": tx.qty1,
            "cost_basis": tx.qty2 / tx.qty1,
            "income": None,
        }

        return result

    def _handle_buy_permuta(self, tx):

        result = {
            "asset_to_pop": tx.asset2,
            "qty_to_pop": tx.qty2,
            "asset_to_push": tx.asset1,
            "qty_to_push": tx.qty1,
            "cost_basis": self.btceur[tx.date] * tx.qty2 / tx.qty1,
            "income": tx.qty2 * self.btceur[tx.date],
        }

        return result

    def _handle_sell(self, tx):

        result = {
            "asset_to_pop": tx.asset1,
            "qty_to_pop": tx.qty1,
            "asset_to_push": None,
            "qty_to_push": None,
            "cost_basis": tx.qty2 / tx.qty1,
            "income": tx.qty2,
        }

        return result

    def _handle_sell_permuta(self, tx):

        result = {
            "asset_to_pop": tx.asset1,
            "qty_to_pop": tx.qty1,
            "asset_to_push": tx.asset2,
            "qty_to_push": tx.qty2,
            "cost_basis": self.btceur[tx.date],
            "income": tx.qty2 * self.btceur[tx.date],
        }

        return result

    def assign_lot(self, asset, qty_to_assign, log=False) -> LotBasket:

        remaining_qty = qty_to_assign

        logger.debug(f"Asset: {asset}\nRemaining qty: {remaining_qty}")

        assigned_lot_basket = LotBasket(asset)

        while remaining_qty > 0:
            # Select the first lot from the asset's lot list

            if self.criterio == "FIFO":
                lot = self.inventory.baskets[asset].lots[0]

            elif self.criterio == "LIFO":
                lot = self.inventory.baskets[asset].lots[-1]

            if lot.qty > remaining_qty:
                # Lot qty more than required, reduce it by qty
                lot.qty -= remaining_qty

                lot_to_assign = Lot(lot.date, lot.asset, remaining_qty, lot.cost)

                assigned_lot_basket.add_lot(lot_to_assign)

                remaining_qty = 0

            else:
                # Lot qty less than or equal to required, pop the first lot FIFO, or last LIfO
                logger.debug(
                    f"Pop lot: {self.inventory.baskets[asset].lots}\nAsset: {asset}\nRemaining qty: {remaining_qty}"
                )
                if self.criterio == "FIFO":
                    lot_to_assign = self.inventory.baskets[asset].lots.pop(0)

                elif self.criterio == "LIFO":
                    lot_to_assign = self.inventory.baskets[asset].lots.pop(-1)

                assigned_lot_basket.add_lot(lot_to_assign)
                remaining_qty -= lot_to_assign.qty

            if log:
                logger.info(
                    f"  Assign lot {lot_to_assign.date:%d%m%y} {lot_to_assign.qty:8.4f} @ {lot_to_assign.cost:8.2f}        ({lot_to_assign.qty * lot_to_assign.cost:8.2f} )"
                )

        logger.debug(
            f"total- assigned: {assigned_lot_basket.total_qty} --- to assign: {qty_to_assign}"
        )

        assert assigned_lot_basket.total_qty - qty_to_assign <= 0.000001

        return assigned_lot_basket

    def record_lot(
        self, date: datetime, asset: str, qty: Decimal, cost_basis: Decimal
    ) -> None:

        self.inventory.add_lot(Lot(date, asset, qty, cost_basis))
        logger.debug(f"                  {Lot(date, asset, qty, cost_basis)}")

    def record_tax_event(self, date, asset, income, assigned_lot_basket: LotBasket):

        cost = assigned_lot_basket.total_cost
        self.tax_events[asset].append(
            {
                "date": date,
                "qty": assigned_lot_basket.total_qty,
                "income": income,
                "cost": cost,
                "result": income - cost,
                "trace": assigned_lot_basket,
            }
        )

        logger.info(
            f"       V.Transmisión: {income:8.2f} - V.Adquisición: {cost:8.2f} - Ganancia P.: {income-cost:8.2f}"
        )

    def year_summary(self):

        logger.info("\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        logger.info(f"\n RESUMEN AÑO {self.year}")
        logger.info("\n| Activo | V.transmisión | V.adquisición | Ganancia P.")

        for asset, events in self.tax_events.items():
            v_transmision = sum(event["income"] for event in events)
            v_adquisicion = sum(event["cost"] for event in events)
            ganancia = sum(event["result"] for event in events)
            logger.info(
                f"|   {asset}  |      {v_transmision:8.2f} |      {v_adquisicion:8.2f} |   {ganancia:8.2f}"
            )

        return

    def _get_precio_btc(self, btc_eur_file: str) -> Dict[datetime, Decimal]:
        # Leer precio de bitcoin diario
        btceur = {}
        try:
            with open(btc_eur_file, "r") as f:
                for line in f:
                    row = line.split()
                    if row[0] == "P":
                        btceur[datetime.strptime(row[1], "%Y-%m-%d")] = Decimal(row[3])
        except FileNotFoundError:
            print("Could not find the BTC price file.")

        return btceur


def main():

    parser = argparse.ArgumentParser(description="Calculate tax.")

    parser.add_argument(
        "--log",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Set the year for tax calculation"
    )
    parser.add_argument(
        "--criterio",
        default="FIFO",
        choices=["FIFO", "LIFO"],
        help="Accounting method for tax calculation. Official is FIFO",
    )
    parser.add_argument("--files", nargs="+", help="List of transaction files")

    parser.add_argument("--log_file", help="set output log file")

    args = parser.parse_args()

    # Set the logging level based on the command line argument
    log_level = getattr(logging, args.log.upper(), None)
    if not isinstance(log_level, int):
        raise ValueError(f"Invalid log level: {args.log}")

    logger.setLevel(log_level)

    # Create console handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter("%(message)s")
    ch.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(ch)

    # If log_file argument provided, create a file handler
    if args.log_file:
        fh = logging.FileHandler(args.log_file)
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        args = parser.parse_args()

    # files = args.files
    # TXS_BTC_FILE = "./transactions.csv"   ## Historico Años 16-18
    # TXS_BTC_FILE = "./transactions2019-bis.csv"   ## Para renta 2019
    # initial_inventory = Inventory()
    TXS_BTC_FILE = (
        "/home/tony/code/cryptotax/data/transactions-bisq.csv"  ## Para Rentas 2020..
    )
    TXS_XMR_FILE = "/home/tony/code/cryptotax/data/localmonero-2020.csv"
    BTC_EUR_FILE = "/home/tony/contabilidad/trading/precios-btc.db"

    initial_inventory = Inventory.from_csv(
        "/home/tony/code/cryptotax/data/inventario-inicial-2020.csv"
    )

    tax_report = TaxEngine(
        year=args.year,
        criterio=args.criterio,
        initial_inventory=initial_inventory,
        btceur_file=BTC_EUR_FILE,
    )

    tax_report.read_transactions([TXS_BTC_FILE, TXS_XMR_FILE])
    tax_report.process_transactions()
    tax_report.year_summary()
    tax_report.inventory.to_csv(f"./output/inv_final-{args.year}.csv")


if __name__ == "__main__":
    main()
