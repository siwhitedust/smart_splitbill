"""
Unit test komprehensif untuk logika kalkulasi Splitbill:
- Satu peserta vs banyak peserta
- Kuantitas lebih dari satu & porsi pecahan (0.5, 1.5)
- Pajak, Service Charge, Diskon, Biaya Tambahan
- Pembulatan Rupiah deterministik dengan Largest Remainder Method
- Validasi alokasi item
"""

from decimal import Decimal
from django.test import SimpleTestCase
from splitbill.services.calculation_service import calculation_service


class CalculationServiceTest(SimpleTestCase):
    def test_single_participant_exact_match(self):
        """Uji satu peserta dengan pesanan kuantitas > 1 dan pajak."""
        bill_info = {
            'restaurant_name': 'Warung Kopi Nusantara',
            'transaction_date': '2026-11-04',
            'tax': '5000',
            'service': '2500',
            'discount': '1000',
            'other_fees': '500',
            'grand_total': '57000',
        }
        items = [
            {'id': 1, 'name': 'Kopi Susu Gula Aren', 'qty': '2', 'price': '25000'},
        ]
        participants = [
            {
                'id': 1,
                'name': 'Budi',
                'items': [{'item_id': 1, 'name': 'Kopi Susu Gula Aren', 'qty': '2', 'price': '25000'}]
            }
        ]

        # Validasi alokasi
        is_valid, unallocated, errors = calculation_service.validate_allocation(items, participants)
        self.assertTrue(is_valid)
        self.assertEqual(len(unallocated), 0)

        # Kalkulasi
        result = calculation_service.calculate_splitbill(bill_info, items, participants)
        self.assertEqual(len(result['participants']), 1)
        budi = result['participants'][0]

        # Subtotal = 50.000, Total = 50.000 + 5.000 + 2.500 + 500 - 1.000 = 57.000
        self.assertEqual(budi['subtotal'], '50000')
        self.assertEqual(budi['tax'], '5000')
        self.assertEqual(budi['service'], '2500')
        self.assertEqual(budi['discount'], '1000')
        self.assertEqual(budi['total'], '57000')
        self.assertEqual(result['total_participants_sum'], '57000')

    def test_multiple_participants_proportional_and_largest_remainder(self):
        """
        Uji banyak peserta dengan proporsi berbeda, pajak, service charge, diskon,
        serta verifikasi metode Largest Remainder untuk pembulatan Rupiah persis sama dengan Grand Total!
        """
        bill_info = {
            'restaurant_name': 'Cafe Mentari',
            'tax': '10000',
            'service': '5000',
            'discount': '7500',
            'other_fees': '0',
            'grand_total': '107500',  # Subtotal 100.000 + 10.000 + 5.000 - 7.500 = 107.500
        }
        items = [
            {'id': 1, 'name': 'Nasi Goreng', 'qty': '2', 'price': '30000'},      # 60.000
            {'id': 2, 'name': 'Mie Kuah', 'qty': '1', 'price': '25000'},         # 25.000
            {'id': 3, 'name': 'Es Teh Manis', 'qty': '3', 'price': '5000'},      # 15.000
        ]
        # Total subtotal = 60.000 + 25.000 + 15.000 = 100.000

        participants = [
            {
                'id': 1,
                'name': 'Andi',
                # Andi pesan 1 Nasi Goreng (30.000) + 1 Es Teh (5.000) = 35.000 (35%)
                'items': [
                    {'item_id': 1, 'name': 'Nasi Goreng', 'qty': '1', 'price': '30000'},
                    {'item_id': 3, 'name': 'Es Teh Manis', 'qty': '1', 'price': '5000'},
                ]
            },
            {
                'id': 2,
                'name': 'Bambang',
                # Bambang pesan 1 Mie Kuah (25.000) + 1 Es Teh (5.000) = 30.000 (30%)
                'items': [
                    {'item_id': 2, 'name': 'Mie Kuah', 'qty': '1', 'price': '25000'},
                    {'item_id': 3, 'name': 'Es Teh Manis', 'qty': '1', 'price': '5000'},
                ]
            },
            {
                'id': 3,
                'name': 'Citra',
                # Citra pesan 1 Nasi Goreng (30.000) + 1 Es Teh (5.000) = 35.000 (35%)
                'items': [
                    {'item_id': 1, 'name': 'Nasi Goreng', 'qty': '1', 'price': '30000'},
                    {'item_id': 3, 'name': 'Es Teh Manis', 'qty': '1', 'price': '5000'},
                ]
            }
        ]

        is_valid, unallocated, errors = calculation_service.validate_allocation(items, participants)
        self.assertTrue(is_valid)
        self.assertEqual(len(unallocated), 0)

        result = calculation_service.calculate_splitbill(bill_info, items, participants)

        # Verifikasi bahwa penjumlahan seluruh peserta sama persis dengan grand_total
        total_sum = sum(Decimal(p['total']) for p in result['participants'])
        self.assertEqual(total_sum, Decimal('107500'))
        self.assertEqual(result['total_participants_sum'], '107500')

    def test_shared_fractional_item(self):
        """Uji pembagian 1 item bersama dengan kuantitas porsi pecahan (misal 0.5 masing-masing)."""
        bill_info = {
            'restaurant_name': 'Pizza Hut',
            'tax': '1000',
            'service': '0',
            'discount': '0',
            'other_fees': '0',
            'grand_total': '11000',
        }
        items = [
            {'id': 1, 'name': 'Pizza Medium', 'qty': '1', 'price': '10000'},
        ]
        participants = [
            {
                'id': 1,
                'name': 'Orang 1',
                'items': [{'item_id': 1, 'name': 'Pizza Medium', 'qty': '0.5', 'price': '10000'}],
            },
            {
                'id': 2,
                'name': 'Orang 2',
                'items': [{'item_id': 1, 'name': 'Pizza Medium', 'qty': '0.5', 'price': '10000'}],
            }
        ]

        is_valid, unallocated, errors = calculation_service.validate_allocation(items, participants)
        self.assertTrue(is_valid)

        result = calculation_service.calculate_splitbill(bill_info, items, participants)
        self.assertEqual(result['participants'][0]['total'], '5500')
        self.assertEqual(result['participants'][1]['total'], '5500')
        self.assertEqual(result['total_participants_sum'], '11000')

    def test_allocation_over_limit_fails(self):
        """Uji jika alokasi melebihi jumlah pembelian pada struk."""
        items = [
            {'id': 1, 'name': 'Es Jeruk', 'qty': '2', 'price': '5000'},
        ]
        participants = [
            {
                'id': 1,
                'name': 'Doni',
                'items': [{'item_id': 1, 'name': 'Es Jeruk', 'qty': '3', 'price': '5000'}],
            }
        ]

        is_valid, unallocated, errors = calculation_service.validate_allocation(items, participants)
        self.assertFalse(is_valid)
        self.assertTrue(any('melebihi' in err for err in errors))

    def test_unallocated_items_reported(self):
        """Uji jika ada item yang belum selesai dialokasikan."""
        items = [
            {'id': 1, 'name': 'Sate Ayam', 'qty': '3', 'price': '20000'},
            {'id': 2, 'name': 'Lontong', 'qty': '2', 'price': '5000'},
        ]
        participants = [
            {
                'id': 1,
                'name': 'Eka',
                'items': [{'item_id': 1, 'name': 'Sate Ayam', 'qty': '2', 'price': '20000'}],
            }
        ]

        is_valid, unallocated, errors = calculation_service.validate_allocation(items, participants)
        self.assertFalse(is_valid)
        self.assertEqual(len(unallocated), 2)  # Sate Ayam sisa 1, Lontong sisa 2

    def test_equal_split_even_division(self):
        """Uji mode bagi rata pembagian pas habis tanpa sisa."""
        bill_info = {
            'restaurant_name': 'Bakso Super Enak',
            'grand_total': '120000',
            'tax': '10000',
            'service': '5000',
            'discount': '0',
            'other_fees': '0',
        }
        res = calculation_service.calculate_equal_split(bill_info, participant_count=3)
        self.assertEqual(res['split_mode'], 'equal')
        self.assertEqual(res['participant_count'], 3)
        self.assertEqual(res['grand_total'], '120000')
        self.assertEqual(res['total_participants_sum'], '120000')

        # Masing-masing harus tepat 40.000
        for p in res['participants']:
            self.assertEqual(p['total'], '40000')
            self.assertEqual(p['total_formatted'], 'Rp40.000')

    def test_equal_split_odd_remainder_precision(self):
        """
        Uji mode bagi rata dengan sisa pembagian ganjil (Rp100.000 dibagi 3 orang).
        Verifikasi presisi Rupiah pas: 1 orang Rp33.334, 2 orang Rp33.333,
        dan total seluruh peserta persis Rp100.000.
        """
        bill_info = {
            'restaurant_name': 'Cafe Hangout',
            'grand_total': '100000',
            'tax': '0',
            'service': '0',
            'discount': '0',
            'other_fees': '0',
        }
        names = ['Andi', 'Budi', 'Caca']
        res = calculation_service.calculate_equal_split(bill_info, participant_count=3, participant_names=names)
        self.assertEqual(res['split_mode'], 'equal')
        self.assertEqual(res['participant_count'], 3)
        self.assertEqual(res['total_participants_sum'], '100000')

        p_totals = [Decimal(p['total']) for p in res['participants']]
        self.assertEqual(sum(p_totals), Decimal('100000'))
        self.assertEqual(res['participants'][0]['name'], 'Andi')
        self.assertEqual(res['participants'][0]['total'], '33334')
        self.assertEqual(res['participants'][1]['total'], '33333')
        self.assertEqual(res['participants'][2]['total'], '33333')

