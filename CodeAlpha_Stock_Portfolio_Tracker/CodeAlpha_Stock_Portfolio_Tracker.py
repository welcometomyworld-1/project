print("\n========== STOCK PORTFOLIO TRACKER ==========\n")

# Hardcoded stock prices
stock_prices = {
    "AAPLE": 180,     # Apple
    "TESLA": 250,     # Tesla
    "GOOGLE": 140,    # Google
    "AMAZON": 130,     # Amazon
    "MICROSOFT": 320      # Microsoft
}

portfolio = {}
total_investment = 0

# Show available stocks
print("Available Stocks:\n")

for stock, price in stock_prices.items():
    print(f"{stock} : ${price}")

print("\n--------------------------------------------")

num_stocks = int(input("\nEnter number of different stocks you want to buy: "))

# Taking user input
for i in range(num_stocks):

    print(f"\nStock {i + 1}")

    stock_name = input("Enter stock name: ").upper()

    if stock_name in stock_prices:

        quantity = int(input("Enter quantity: "))

        # Save in portfolio
        portfolio[stock_name] = quantity

    else:
        print(" Stock not available! Skipping...")

print("\n========== PORTFOLIO SUMMARY ==========\n")

for stock, quantity in portfolio.items():

    price = stock_prices[stock]

    investment = price * quantity

    total_investment += investment

    print(f"Stock Name : {stock}")
    print(f"Quantity   : {quantity}")
    print(f"Price      : ${price}")
    print(f"Investment : ${investment}")
    print("-----------------------------------")

# Final Total
print(f"\n Total Investment Value = ${total_investment}")


file = open("portfolio_summary.txt", "w")

file.write("========== STOCK PORTFOLIO SUMMARY ==========\n\n")

for stock, quantity in portfolio.items():

    price = stock_prices[stock]

    investment = price * quantity

    file.write(f"Stock Name : {stock}\n")
    file.write(f"Quantity   : {quantity}\n")
    file.write(f"Price      : ${price}\n")
    file.write(f"Investment : ${investment}\n")
    file.write("-----------------------------------\n")

file.write(f"\nTotal Investment Value = ${total_investment}")

file.close()

print("\n Portfolio summary saved in 'portfolio_summary.txt'")
print("\n========== THANK YOU ==========")