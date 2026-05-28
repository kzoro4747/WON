import traceback
from image_generator import generate_settlement_image
from calculator import Family

# Mock data similar to main.py
families = {
    "가율": Family("가율", 4),
    "소율": Family("소율", 3),
}

expenses = [
    {
        "item_name": "첫날 장보기",
        "payer_name": "가율",
        "amount": 49000,
        "participants": ["가율", "소율"],
        "split_by_member": False,
        "memo": "맥주,그릴",
        "custom_shares": None
    }
]

transfers = [("소율", "가율", 19658)]
total_spent = 49000

try:
    print("Generating image...")
    img_bytes = generate_settlement_image(families, expenses, transfers, total_spent)
    print("Success! Image generated.")
except Exception as e:
    print("Error during image generation:")
    traceback.print_exc()
