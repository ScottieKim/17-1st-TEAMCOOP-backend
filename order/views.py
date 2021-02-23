import json
from datetime       import datetime

from django.http    import JsonResponse
from django.views   import View

from user.utils     import login_decorator
from user.models    import Address
from product.models import ProductStock 
from .models        import (
    Order,
    OrderProductStock,
)

class CartView(View):
     @login_decorator
     def get(self, request):
        user = request.user
        
        if not Order.objects.filter(user=user, order_status_id=1).exists():
            return JsonResponse({"message": "EMPTY"}, status=200)
        
        order_exist          = Order.objects.get(user=user, order_status_id=1)
        order_products_exist = order_exist.orderproductstock_set.filter(order=order_exist)
        
        cart_product_list = []
        for order_product_exist in order_products_exist:
            product_SSP  = order_product_exist.product_stock 
            product      = product_SSP.product
            product_info = {
                "category"        : product.category.menu.name,
                "productId"       : product.id,
                "productName"     : product.name,
                "productSubName"  : product.sub_name,
                "productStockId"  : product_SSP.id,
                "productSize"     : product_SSP.size,
                "productPrice"    : product_SSP.price,
                "productStock"    : product_SSP.stock,
                "productImageUrl" : product.image_set.get(is_main=True).image_url,
                "productQuantity" : order_product_exist.quantity
            }
            cart_product_list.append(product_info)

        data = {
            "orderNumber": order_exist.order_number,
            "carts": cart_product_list,
        }

        return JsonResponse({"data": data, "message": "SUCCESS"}, status=200)

class CartDetailView(View):
    @login_decorator
    def post(self, request, product_stock_id):
        data         = json.loads(request.body)
        user         = request.user
        product_id   = data.get('productId', None)
        size_new     = data.get('productSize', None)
        quantity_new = data.get('productQuantity', None)
        
        if not (product_id and quantity_new):
            return JsonResponse({"message": "KEY_ERROR"}, status=400)

        if not ProductStock.objects.filter(id=product_stock_id):
            return JsonResponse({"message": "DOES_NOT_EXIST"}, status=404)

        if not ProductStock.objects.filter(product_id=product_id, size=size_new):
            return JsonResponse({"message": "DOES_NOT_EXIST"}, status=400)
        
        order_exist          = Order.objects.get(user=user, order_status_id=1)
        target_order_product = OrderProductStock.objects.filter(order=order_exist, product_stock_id=product_stock_id)
        
        # invalid product check
        if not target_order_product:
            return JsonResponse({"message": "DOES_NOT_EXIST"}, status=400)
        
        target_order_product      = target_order_product[0] 
        target_order_product_size = target_order_product.product_stock.size
        product_new               = ProductStock.objects.get(product_id=product_id, size=size_new)

        # 변경할 상품이 이미 OrderProductStock에 존재하는 경우
        if target_order_product_size != size_new: 
            order_product_already_exist = OrderProductStock.objects.filter(order=order_exist, product_stock=product_new) 

            if order_product_already_exist:

                if bool(product_new.stock - quantity_new < 0):
                    return JsonResponse({"message": "OUT_OF_STOCK"}, status=200)

                order_product_already_exist[0].quantity = quantity_new
                order_product_already_exist[0].save()

                # 원래 있던 상품은 새로 바꿀 상품이 이미 존재하는게 있으므로 삭제 
                target_order_product.delete()
                return JsonResponse({"message": "SUCCESS"}, status=200)

        if bool(product_new.stock - int(quantity_new) < 0):
            return JsonResponse({"message": "OUT_OF_STOCK"}, status=200)

        target_order_product.product_stock = product_new
        target_order_product.quantity      = quantity_new
        target_order_product.save()

        return JsonResponse({"message": "SUCCESS"}, status=200)

    @login_decorator
    def delete(self, request, product_stock_id):

        if not ProductStock.objects.filter(id=product_stock_id):
            return JsonResponse({"message": "DOES_NOT_EXIST"}, status=404)

        user          = request.user
        order_exist   = Order.objects.get(user=user, order_status_id=1)
        product_exist = ProductStock.objects.get(id=product_stock_id)

        target_order_product = OrderProductStock.objects.filter(order=order_exist, product_stock=product_exist)
        if not target_order_product:
            return JsonResponse({"message": "DOES_NOT_EXIST"}, status=404)

        target_order_product[0].delete()

        # 장바구니에 상품이 없을 경우 order 정보 삭제
        if not OrderProductStock.objects.filter(order=order_exist):
            order_exist.delete()

        return JsonResponse({"message": "SUCCESS"}, status=200) 

