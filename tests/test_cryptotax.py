#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import pytest
from datetime import datetime
from csv import DictReader
from io import StringIO
from decimal import Decimal

from cryptotax import Lot, LotBasket, Inventory, TaxEngine, Transaction


def setup_lot():
    lot1 = Lot(datetime(2019, 11, 6), "XMR", 5, 40)
    lot2 = Lot(datetime(2019, 12, 2), "XMR", 5, 50)
    lot3 = Lot(datetime(2020, 12, 2), "BTC", 1, 10000)
    return lot1, lot2, lot3


def setup_basket():
    lot1, lot2, lot3 = setup_lot()
    basket1 = LotBasket("XMR")
    basket1.add_lot(lot1)
    basket1.add_lot(lot2)

    basket2 = LotBasket("BTC")
    basket2.add_lot(lot3)
    return basket1, basket2


def setup_inventory():
    basket1, basket2 = setup_basket()
    inventory = Inventory()
    inventory.add_basket(basket1)
    inventory.add_basket(basket2)
    return inventory


def test_lot():
    lot1, _, _ = setup_lot()
    assert lot1.date == datetime(2019, 11, 6)
    assert lot1.asset == "XMR"
    assert lot1.qty == 5
    assert lot1.cost == 40


def test_lot_basket_total_qty():
    basket, _ = setup_basket()
    assert basket.total_qty == 10


def test_lot_basket_add_wrong_lot():
    lot1, _, lot3 = setup_lot()
    basket = LotBasket("XMR")
    basket.add_lot(lot1)

    with pytest.raises(ValueError):
        """
        Intentamos incluir un lote de bitcoin
        en una canasta de monero
        """
        basket.add_lot(lot3)


def test_lot_basket_total_cost():
    basket, _ = setup_basket()
    assert basket.total_cost == 450


def test_lot_basket_avg_cost():
    basket, _ = setup_basket()
    assert basket.avg_cost == 45


def test_inventory_add_basket():
    basket1, basket2 = setup_basket()
    inventory = Inventory()
    inventory.add_basket(basket1)
    inventory.add_basket(basket2)
    assert set(inventory.baskets.keys()) == set(["XMR", "BTC"])


def test_inventory_balance():
    inventory = Inventory()
    basket1, basket2 = setup_basket()
    inventory.add_basket(basket1)
    assert inventory.balance == [
        {"XMR": {"qty": 10, "basis": 45}},
    ]

    inventory.add_basket(basket2)
    assert inventory.balance == [
        {"XMR": {"qty": 10, "basis": 45}},
        {"BTC": {"qty": 1, "basis": 10000}},
    ]


# Test case for checking the total quantity of XMR and BTC in the inventory
def test_inventory_total_qty():
    inventory = setup_inventory()
    assert inventory.baskets["XMR"].total_qty == Decimal("10")
    assert inventory.baskets["BTC"].total_qty == Decimal("1")


# Test case for checking the basis of XMR and BTC in the inventory
def test_inventory_total_cost():
    inventory = setup_inventory()
    assert inventory.baskets["XMR"].total_cost == Decimal("450")
    assert inventory.baskets["BTC"].total_cost == Decimal("10000")


# Create a setup function for the TaxYear
def setup_tax_engine():
    inventory = setup_inventory()
    transactions = [
        Transaction(
            "tx1",
            datetime(2020, 1, 10),
            "Buy",
            Decimal(5.0),
            "XMR",
            Decimal(300.0),
            "EUR",
        ),
        Transaction(
            "tx2",
            datetime(2020, 2, 20),
            "Sell",
            Decimal(10.0),
            "XMR",
            Decimal(900.0),
            "EUR",
        ),
    ]
    return TaxEngine(
        year=2020,
        criterio="FIFO",
        initial_inventory=inventory,
        transactions=transactions,
        base_asset="EUR",
    )


# Test case for checking the process_transactions method
def test_process_transactions():
    tax_engine = setup_tax_engine()
    tax_engine.process_transactions()
    assert tax_engine.inventory.total_qty("XMR") == 5
    assert tax_engine.inventory.total_qty("BTC") == 1
    assert len(tax_engine.tax_events) == 1


def test_process_transactions_buy():
    """TODO"""
    pass


def test_process_transactions_buy_permuta():
    """TODO"""
    pass


def test_process_transactions_sell():
    """TODO"""
    pass


def test_process_transactions_sell_permuta():
    """TODO"""
    pass


def test_process_transactions_sell_more_qty():
    """
    TODO
    Sell more qty than what is in inventory should raise an Exception
    """
    pass


# Test case for checking the record_tax_event method
def test_record_tax_event():
    """
    Inventario inicial XMR:
    # XMR: 5 @ 40 ( 200 EUR )
    # XMR: 5 @ 50 ( 250 EUR )

    Venta:   7 XMR       @@  450
    # As.1: -5 XMR @ 40  @@ -200
    # As.2: -2 XMR @ 50  @@ -100
    #
    # Total Coste: 300
    # Resultado:   100
    """
    tax_engine = setup_tax_engine()
    tx = Transaction(
        "tx1", datetime(2020, 2, 20), "Sell", Decimal(7.0), "XMR", Decimal(450.0), "EUR"
    )
    lot_basket = tax_engine.assign_lot(tx.asset1, tx.qty1)
    tax_engine.record_tax_event(tx.date, tx.asset1, tx.qty2, lot_basket)
    assert len(tax_engine.tax_events) == 1
    assert tax_engine.inventory.baskets["XMR"].total_qty == 3
    assert tax_engine.inventory.baskets["XMR"].total_cost == 150
    assert tax_engine.tax_events["XMR"][0]["cost"] == 300
    assert tax_engine.tax_events["XMR"][0]["result"] == 150


# Test case for checking the assign_lot method
def test_assign_lot():
    tax_engine = setup_tax_engine()
    tx = Transaction(
        "tx1",
        datetime(2020, 2, 20),
        "Sell",
        Decimal(10.0),
        "XMR",
        Decimal(400.0),
        "EUR",
    )

    lot_basket = tax_engine.assign_lot("XMR", 10.0)
    assert lot_basket.total_qty == 10.0
    assert lot_basket.total_cost == 450
