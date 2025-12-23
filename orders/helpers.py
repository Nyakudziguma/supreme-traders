




def handle_order(trader, amount, account_number, email, ecocash_number='', ecocash_name='', code='', token=''):
    try:
        # Standardize CR number
        if not account_number.upper().startswith('CR'):
            account_number = 'CR' + account_number.lstrip('crCR')

        # Create the order object (sell)
        order = OrderProcessor.initiate_transaction(
            trader, "Sell", amount, account_number, ecocash_number, ecocash_name
        )

        # ----- WITHDRAW FROM DERIV -----
        try:
            withdrawal_response = asyncio.run(
                process_withdrawal(amount, account_number, code, token)
            )

            print("Withdrawal Response:", withdrawal_response)

            paymentagent_transfer = (
                withdrawal_response.get('paymentagent_withdraw')
                if withdrawal_response else None
            )

            trans_status = "Failed"
            with db_transaction.atomic():

                # ---------------- SUCCESS ----------------
                if paymentagent_transfer == 1:
                    OrderProcessor.process_order(order.id, 'Completed')
                    trans_status = "Successful"

                    # Clean phone
                    clean_number = re.sub(r"\s+", "", ecocash_number)

                    # Send SMS
                    sms_response = send_sms(clean_number, amount)
                    print("SMS API Response:", sms_response)

                # ---------------- FAILURE ----------------
                else:
                    OrderProcessor.process_order(order.id, 'Failed')

                deriv_id = withdrawal_response.get('transaction_id') if withdrawal_response else None
                extras = json.dumps(withdrawal_response)

                charge = order.charge

                # Deduct from main balance
                balance = Balance.objects.filter(name='main').first()
                balance.balance -= amount
                balance.save()

                # Create transaction
                transaction = Transaction.objects.create(
                    order=order,
                    trader=trader,
                    transaction_type="Sell",
                    amount=amount,
                    charge=charge,
                    status=trans_status,
                    deriv_id=deriv_id,
                    extras=extras
                )

                # ---------------- SUCCESS FLOW ----------------
                if trans_status == 'Successful':
                    Withdrawals.objects.create(
                        trader=trader,
                        transaction=transaction,
                        amount=amount
                    )

                    # Notify support
                    message = (
                        f"User {trader.phone_number} with ecocash number {ecocash_number} "
                        f"has completed a withdrawal transaction with reference {transaction.reference} "
                        f"and is now waiting for disbursement."
                    )

                    try:
                        recipients = list(Account.objects.filter(user_type="support"))
                        if recipients:
                            recipient = random.choice(recipients)
                            OrderProcessor.create_notification(recipient, message, transaction)
                        else:
                            raise Account.DoesNotExist
                    except Account.DoesNotExist:
                        AuditLog.objects.create(
                            trader=trader,
                            action=f"Failed to send withdrawal notification for {transaction.reference}"
                        )

                    # Ledger Entries
                    deriv_account = LedgerAccount.objects.get(name="Deriv Inventory")
                    bank_account = LedgerAccount.objects.get(name="Bank Account")
                    revenue_account = LedgerAccount.objects.get(name="Deriv Revenue")
                    forex_inventory_account = LedgerAccount.objects.get(name="Forex Inventory")
                    charges = LedgerAccount.objects.get(name="Bank Charges")

                    LedgerEntry.objects.create(
                        transaction=transaction,
                        account=bank_account,
                        is_debit=False,
                        amount=order.amount
                    )

                    LedgerEntry.objects.create(
                        transaction=transaction,
                        account=charges,
                        is_debit=False,
                        amount=0
                    )

                    LedgerEntry.objects.create(
                        transaction=transaction,
                        account=deriv_account,
                        is_debit=True,
                        amount=order.amount
                    )

                    LedgerEntry.objects.create(
                        transaction=transaction,
                        account=revenue_account,
                        is_debit=True,
                        amount=order.amount
                    )

                    LedgerEntry.objects.create(
                        transaction=transaction,
                        account=forex_inventory_account,
                        is_debit=False,
                        amount=order.amount
                    )

                    AuditLog.objects.create(
                        trader=trader,
                        action=f"Transaction ID {transaction.id} for {amount} with charge {charge} created."
                    )

                    # WhatsApp success message
                    message = (
                        "*Order Completed Successfully* \n\n"
                        "✅ Your order has been **successfully processed**.\n\n"
                        f"📦 Order Number: {order.order_number} \n"
                        f"🔖 Transaction Reference: {transaction.reference} \n\n"
                        "Thank you for choosing us!"
                    )
                    Home(order.trader.phone_number, message)

                else:
                    # ---------------- FAILED FLOW ----------------
                    message = (
                        "*⚠️ Order Processing Failed* \n\n"
                        f"📦 Order Number: {order.order_number} \n"
                        f"🔖 Transaction Reference: {transaction.reference} \n\n"
                        "Please try again or contact support."
                    )
                    Home(order.trader.phone_number, message)

                return transaction

        except Exception as e:
            print("Withdrawal Processing Error:", e)

            with db_transaction.atomic():
                transaction = Transaction.objects.create(
                    order=order,
                    trader=trader,
                    transaction_type="Sell",
                    amount=amount,
                    charge=0,
                    status='Failed',
                    extras=json.dumps({"error": str(e)})
                )

                AuditLog.objects.create(
                    trader=trader,
                    action=f"Transaction {transaction.id} failed → {str(e)}"
                )

                # Refund internal balance
                trader_balance = Balance.objects.filter(name=transaction.trader.username).first()
                if trader_balance:
                    trader_balance.balance += transaction.amount
                    trader_balance.save()

                Home(
                    order.trader.phone_number,
                    "*⚠️ Order Processing Failed* \n\n"
                    f"📦 Order: {order.order_number} \n"
                    "Please try again or contact support."
                )

                return transaction

    except Exception as e:
        print("FATAL SELL ERROR:", e)
        raise
