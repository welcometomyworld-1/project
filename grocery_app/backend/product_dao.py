import mysql.connector

cnx = mysql.connector.connect(user='root', password='Spy@123',
                              host='127.0.0.1',
                              database='gc')
cursor = cnx.cursor()
query = "SELECT * FROM gc.order_detials;SELECT * FROM gc.order_detials;"
cursor.execute(query)

for (product_id, name, uom_id, price_per_unit) in cursor:
    print(product_id, name, uom_id, price_per_unit)
cnx.close()
