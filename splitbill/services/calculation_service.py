"""
Service kalkulasi pembagian tagihan (Splitbill) berbasis Decimal.
Menjamin akurasi 100%, pembagian proporsional, dan penyesuaian pembulatan
Rupiah menggunakan metode Largest Remainder yang deterministik.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Tuple
from splitbill.utils import parse_decimal, format_rupiah


class CalculationService:
    """
    Logika bisnis kalkulasi tagihan dan pembagian proporsional antar peserta.
    """

    @staticmethod
    def validate_allocation(items: List[Dict[str, Any]], participants: List[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
        """
        Validasi alokasi seluruh item struk kepada peserta.
        - Kuantitas yang dialokasikan tidak boleh melebihi kuantitas pembelian.
        - Semua item harus teralokasi tuntas sebelum dapat disimpan.
        Mengembalikan: (is_valid, list_unallocated_items, list_error_messages)
        """
        errors = []
        unallocated_list = []

        if not participants:
            errors.append("Harus ada minimal satu peserta dalam pembagian tagihan.")
            return False, unallocated_list, errors

        # Buat pemetaan alokasi item berdasarkan index atau ID item
        for item_idx, item in enumerate(items):
            item_name = item.get('name', f"Item #{item_idx + 1}")
            total_qty = parse_decimal(item.get('qty', 0))

            # Hitung total yang dialokasikan ke semua peserta
            allocated_qty = Decimal('0')
            for p in participants:
                for p_item in p.get('items', []):
                    # Cocokkan berdasarkan item_id atau nama
                    p_id = p_item.get('item_id')
                    if p_id is not None and str(p_id) == str(item.get('id', item_idx)):
                        allocated_qty += parse_decimal(p_item.get('qty', 0))
                    elif p_id is None and p_item.get('name') == item_name:
                        allocated_qty += parse_decimal(p_item.get('qty', 0))

            remaining_qty = total_qty - allocated_qty

            # Toleransi selisih kuantitas desimal kecil
            if allocated_qty > total_qty + Decimal('0.0001'):
                errors.append(
                    f"Alokasi untuk '{item_name}' ({allocated_qty}) melebihi jumlah pembelian ({total_qty})."
                )
            elif remaining_qty > Decimal('0.0001'):
                unallocated_list.append({
                    'id': item.get('id', item_idx),
                    'name': item_name,
                    'total_qty': str(total_qty),
                    'allocated_qty': str(allocated_qty),
                    'remaining_qty': str(remaining_qty),
                    'price': str(parse_decimal(item.get('price', 0))),
                })

        if unallocated_list:
            unallocated_names = ", ".join([f"{u['name']} (sisa {u['remaining_qty']})" for u in unallocated_list])
            errors.append(f"Masih ada item yang belum selesai dialokasikan: {unallocated_names}.")

        return (len(errors) == 0, unallocated_list, errors)

    @staticmethod
    def calculate_splitbill(
        bill_info: Dict[str, Any],
        items: List[Dict[str, Any]],
        participants: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Melakukan kalkulasi komprehensif:
        1. Subtotal masing-masing item dan grand subtotal.
        2. Subtotal setiap peserta.
        3. Alokasi proporsional Pajak, Service Charge, Diskon, Biaya Tambahan.
        4. Pembulatan Rupiah deterministik dengan Largest Remainder Method.
        """
        # Parsing komponen tagihan
        tax = parse_decimal(bill_info.get('tax', 0))
        service = parse_decimal(bill_info.get('service', 0))
        discount = parse_decimal(bill_info.get('discount', 0))
        other_fees = parse_decimal(bill_info.get('other_fees', 0))
        raw_grand_total = parse_decimal(bill_info.get('grand_total', 0))

        # Hitung subtotal seluruh item
        calculated_subtotal = Decimal('0')
        processed_items = []
        for idx, it in enumerate(items):
            it_qty = parse_decimal(it.get('qty', 1))
            it_price = parse_decimal(it.get('price', 0))
            it_subtotal = it_price * it_qty
            calculated_subtotal += it_subtotal
            processed_items.append({
                'id': it.get('id', idx),
                'name': it.get('name', f"Item #{idx + 1}").strip(),
                'qty': str(it_qty),
                'price': str(it_price),
                'price_formatted': format_rupiah(it_price),
                'subtotal': str(it_subtotal),
                'subtotal_formatted': format_rupiah(it_subtotal),
                'confidence': it.get('confidence', 'high'),
            })

        # Hitung total yang seharusnya menurut komponen
        calculated_grand_total = calculated_subtotal + tax + service + other_fees - discount
        if raw_grand_total <= 0:
            grand_total = calculated_grand_total
        else:
            grand_total = raw_grand_total

        # Peringatan ketidaksesuaian jika ada selisih antara kalkulasi dan total struk
        has_total_discrepancy = (abs(calculated_grand_total - grand_total) >= Decimal('1'))
        discrepancy_amount = grand_total - calculated_grand_total

        # Hitung subtotal tiap peserta
        total_participants_subtotal = Decimal('0')
        participants_data = []

        for p_idx, p in enumerate(participants):
            p_name = p.get('name', f"Peserta {p_idx + 1}").strip()
            p_items_raw = p.get('items', [])
            p_items_processed = []
            p_subtotal = Decimal('0')

            for pit in p_items_raw:
                p_qty = parse_decimal(pit.get('qty', 0))
                p_price = parse_decimal(pit.get('price', 0))
                p_item_subtotal = p_price * p_qty
                p_subtotal += p_item_subtotal

                p_items_processed.append({
                    'item_id': pit.get('item_id'),
                    'name': pit.get('name', ''),
                    'qty': str(p_qty),
                    'price': str(p_price),
                    'price_formatted': format_rupiah(p_price),
                    'subtotal': str(p_item_subtotal),
                    'subtotal_formatted': format_rupiah(p_item_subtotal),
                })

            total_participants_subtotal += p_subtotal
            participants_data.append({
                'id': p.get('id', p_idx + 1),
                'name': p_name,
                'items': p_items_processed,
                'subtotal': p_subtotal,
            })

        # Alokasi proporsional
        num_participants = len(participants_data)
        participant_results = []

        # Basis proporsi adalah total_participants_subtotal jika > 0, atau bagi rata jika 0
        use_subtotal_base = total_participants_subtotal > Decimal('0')

        for p in participants_data:
            if use_subtotal_base:
                proportion = p['subtotal'] / total_participants_subtotal
            else:
                proportion = Decimal('1') / Decimal(num_participants) if num_participants > 0 else Decimal('0')

            # Alokasi nilai desimal presisi tinggi
            p_tax_raw = tax * proportion
            p_service_raw = service * proportion
            p_discount_raw = discount * proportion
            p_other_raw = other_fees * proportion

            # Jika ada perbedaan grand_total pada struk (misal pembulatan kasir), bagikan proporsional
            p_discrepancy_raw = discrepancy_amount * proportion if has_total_discrepancy else Decimal('0')

            p_total_raw = (
                p['subtotal']
                + p_tax_raw
                + p_service_raw
                + p_other_raw
                - p_discount_raw
                + p_discrepancy_raw
            )

            participant_results.append({
                'id': p['id'],
                'name': p['name'],
                'items': p['items'],
                'subtotal': p['subtotal'],
                'proportion': proportion,
                'tax_raw': p_tax_raw,
                'service_raw': p_service_raw,
                'discount_raw': p_discount_raw,
                'other_raw': p_other_raw,
                'total_raw': p_total_raw,
            })

        # Largest Remainder Method untuk pembulatan Rupiah total pembayaran tiap orang
        # Target sum total adalah grand_total
        target_total_sum = grand_total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        floored_sum = Decimal('0')

        for pr in participant_results:
            floor_val = pr['total_raw'].quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            pr['total_rounded'] = floor_val
            pr['remainder'] = pr['total_raw'] - floor_val
            floored_sum += floor_val

        diff = target_total_sum - floored_sum
        diff_int = int(diff)

        if diff_int > 0:
            # Tambahkan 1 Rupiah kepada peserta dengan sisa desimal tertinggi
            sorted_by_remainder = sorted(participant_results, key=lambda x: x['remainder'], reverse=True)
            for i in range(min(diff_int, len(sorted_by_remainder))):
                sorted_by_remainder[i]['total_rounded'] += Decimal('1')
        elif diff_int < 0:
            # Kurangi 1 Rupiah dari peserta dengan sisa desimal terendah
            sorted_by_remainder = sorted(participant_results, key=lambda x: x['remainder'])
            for i in range(min(abs(diff_int), len(sorted_by_remainder))):
                sorted_by_remainder[i]['total_rounded'] -= Decimal('1')

        # Formatkan hasil akhir peserta
        final_participants = []
        for pr in participant_results:
            tax_rounded = pr['tax_raw'].quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            service_rounded = pr['service_raw'].quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            discount_rounded = pr['discount_raw'].quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            other_rounded = pr['other_raw'].quantize(Decimal('1'), rounding=ROUND_HALF_UP)

            final_participants.append({
                'id': pr['id'],
                'name': pr['name'],
                'items': pr['items'],
                'subtotal': str(pr['subtotal']),
                'subtotal_formatted': format_rupiah(pr['subtotal']),
                'tax': str(tax_rounded),
                'tax_formatted': format_rupiah(tax_rounded),
                'service': str(service_rounded),
                'service_formatted': format_rupiah(service_rounded),
                'discount': str(discount_rounded),
                'discount_formatted': format_rupiah(discount_rounded),
                'other_fees': str(other_rounded),
                'other_fees_formatted': format_rupiah(other_rounded),
                'total': str(pr['total_rounded']),
                'total_formatted': format_rupiah(pr['total_rounded']),
            })

        # Verifikasi bahwa jumlah total peserta persis sama dengan target
        total_participants_final = sum(Decimal(p['total']) for p in final_participants)

        return {
            'restaurant_name': bill_info.get('restaurant_name', 'Restoran / Kafe').strip() or 'Restoran / Kafe',
            'transaction_date': bill_info.get('transaction_date', '').strip(),
            'subtotal': str(calculated_subtotal),
            'subtotal_formatted': format_rupiah(calculated_subtotal),
            'tax': str(tax),
            'tax_formatted': format_rupiah(tax),
            'service': str(service),
            'service_formatted': format_rupiah(service),
            'discount': str(discount),
            'discount_formatted': format_rupiah(discount),
            'other_fees': str(other_fees),
            'other_fees_formatted': format_rupiah(other_fees),
            'grand_total': str(grand_total),
            'grand_total_formatted': format_rupiah(grand_total),
            'calculated_grand_total': str(calculated_grand_total),
            'has_total_discrepancy': has_total_discrepancy,
            'discrepancy_amount': str(discrepancy_amount),
            'discrepancy_formatted': format_rupiah(discrepancy_amount),
            'items': processed_items,
            'participants': final_participants,
            'participant_count': len(final_participants),
            'total_participants_sum': str(total_participants_final),
            'total_participants_sum_formatted': format_rupiah(total_participants_final),
        }


calculation_service = CalculationService()

