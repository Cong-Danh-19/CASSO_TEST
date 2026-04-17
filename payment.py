import os
import time
from payos import PayOS
from payos.type import PaymentData  
from dotenv import load_dotenv

# Load các biến môi trường
load_dotenv()

# Khởi tạo PayOS
payos = PayOS(
    client_id=os.getenv("PAYOS_CLIENT_ID"),
    api_key=os.getenv("PAYOS_API_KEY"),
    checksum_key=os.getenv("PAYOS_CHECKSUM_KEY")
)

def create_order_payment(amount, description):
    # Tạo mã đơn hàng (phải là số nguyên)
    order_code = int(time.time()) 
    
    # Sử dụng PaymentData từ payos.type
    payment_data = PaymentData(
        orderCode=order_code,
        amount=amount,
        description=description,
        cancelUrl="https://your-domain.com/cancel",
        returnUrl="https://your-domain.com/success"
    )

    try:
        response = payos.createPaymentLink(payment_data)
        # Trả về link thanh toán 
        return response.checkoutUrl
    except Exception as e:
        print(f"Lỗi PayOS: {e}")
        return None, None