import json
from datetime import datetime
from random   import randint

from django.http      import JsonResponse, HttpResponse
from django.views     import View
from django.db.models import Q

from user.utils     import login_decorator
from product.models import Category, Product, ProductStock, Goal
from order.models   import Order, OrderProductStock

class ProductListView(View):
    def make_product_info_list(self, products):
        product_info_list  = []
        for product in products:
            goals              = product.goal.all()      
            product_SSPs       = product.productstock_set.all()  
            goal_name_list     = [goal.name for goal in goals]
            product_price_list = [product_SSP.price for product_SSP in product_SSPs] 
            product_stock_list = [product_SSP.stock for product_SSP in product_SSPs] 
            product_size_list  = [product_SSP.size for product_SSP in product_SSPs]
            is_soldout         = bool(sum(product_stock_list) == 0)
            
            product_info = {
                "id"           : product.id,
                "displayTitle" : product.name,
                "subTitle"     : product.sub_name,
                "imageUrl"     : product.image_set.get(is_main=True).image_url,
                "symbolURL"    : goal_name_list,
                "description"  : product.description,
                "displayPrice" : product_price_list,
                "displaySize"  : product_size_list,
                "isNew"        : product.is_new,
                "isSoldout"    : is_soldout
            }
            product_info_list.append(product_info)

        return product_info_list

    def get(self, request):
        sort     = request.GET.get('sort', None)
        q=Q()
        if sort:
            q.add(Q(name__icontains=sort),q.OR)
        categories = Category.objects.filter(q)

        if categories: 
            result = [{
                "id"          : category.id,
                "subcategory" : {
                    "title"       : category.name,
                    "description" : category.description,
                },
                "item"         : self.make_product_info_list(products=Product.objects.filter(category=category)) 
            } for category in categories]
j
            return JsonResponse({"data": result, "message": "SUCCESS"}, status=200)

        if Goal.objects.filter(name__icontains=sort).exists():
            goal     = Goal.objects.get(name__icontains=sort)
            products = Product.objects.filter(goal=goal)
            result   = self.make_product_info_list(products=products) 
            
            return JsonResponse({"data": result, "message": "SUCCESS"}, status=200)

        products = Product.objects.filter(is_new=bool(sort == 'new'))
        result   = self.make_product_info_list(products=products) 

        return JsonResponse({"data": result, "message": "SUCCESS"}, status=200)
        
class ProductDetailView(View):
    def get(self, request, product_id):
        if not Product.objects.filter(id=product_id).exists():
            return JsonResponse({'message': 'DOES_NOT_EXIST'}, status=404)

        context  = {}
        product  = Product.objects.get(id=product_id)
        category = product.category.menu.name
        
        context['category']            = category
        context['id']                  = product.id
        context['productImageSrc']     = product.image_set.get(is_main=False).image_url
        context['productCardImageSrc'] = product.image_set.get(is_main=True).image_url

        # is_vegan, is_vegeterian
        vegan_level = product.vegan_level_id
        if vegan_level == 1:
            is_vegan      = True
            is_vegeterian = False
        elif vegan_level == 2:
            is_vegan      = False
            is_vegeterian = True
        else:
            is_vegan      = False
            is_vegeterian = False

        context['isVegan']        = is_vegan
        context['isVegetarian']   = is_vegeterian
        context['healthGoalList'] = [goal.name for goal in product.goal.all()]
        context['title']          = product.name
        context['subTitle']       = product.sub_name
        context['description']    = product.description
        context['nutritionLink']  = product.nutrition_url
        context['allergyList']    = [allergy.name for allergy in product.allergy.all()]

        # size, price
        product_SSPs = ProductStock.objects.filter(product=product)  # SSP: siz e, stock, price
        if category == 'vitamins':
            price      = product_SSPs[0].price   
            is_soldout = bool(product_SSPs[0].stock == 0)
        else:
            price = {
                product_SSPs[0].size : product_SSPs[0].price,
                product_SSPs[1].size : product_SSPs[1].price
            }
            is_soldout = {
                product_SSPs[0].size : bool(product_SSPs[0].stock == 0),
                product_SSPs[1].size : bool(product_SSPs[1].stock == 0)
            }

        context['productPrice']     = price
        context['isSoldOut']        = is_soldout
        context['dietaryHabitList'] = [dietary_habit.name for dietary_habit in product.dietary_habit.all()]

        # similar products
        similar_product_list = []
        goals_product        = product.goal.all()
        for goal_product in goals_product:
            similar_products = goal_product.product_set.exclude(id=product_id)

            for similar_product in similar_products:
                similar_product_info = {
                        'id'             : similar_product.id,
                        'title'          : similar_product.name,
                        'subTitle'       : similar_product.sub_name,
                        'imageUrl'       : similar_product.image_set.get(is_main=True).image_url,
                        'healthGoalList' : [goal.name for goal in similar_product.goal.all()]
                }
                similar_product_list.append(similar_product_info)

        context['similarProduct'] = similar_product_list[:2] 

        return JsonResponse({"data": context, "message": "SUCCESS"}, status=200)
        

#Add 눌렀을 때 
class ProductToCartView(View):
    @login_decorator
    def post(self, request):
            data          = json.loads(request.body)
            user          = request.user
            product_id    = data.get('productId', None)
            product_size  = data.get('productSize', None)
            product_price = data.get('productPrice', None)

            if not (product_id and product_price): 
                return JsonResponse({"message": "KEY_ERROR"}, status=400)            

            product_price = float(product_price)

            # orders insert
            if not Order.objects.filter(user=user, order_status_id=1).exists():
                shipping_cost = 5 if product_price < 20 else 0
                order         = Order.objects.create(  # order_info
                    user            = user,
                    order_number    = datetime.today().strftime("%Y%m%d") + str(randint(1000, 10000)),
                    order_status_id = 1,
                    sub_total_cost  = product_price,
                    shipping_cost   = shipping_cost,
                    total_cost      = product_price + shipping_cost
                )
            else:
                order = Order.objects.get(user=user, order_status_id=1)
                order.sub_total_cost = float(order.sub_total_cost) + product_price
                order.shipping_cost  = 5 if order.sub_total_cost < 20 else 0
                order.total_cost     = float(order.sub_total_cost) + order.shipping_cost
                order.save()
            
            if not ProductStock.objects.filter(product_id=product_id, size=product_size):
                return JsonResponse({"message": "PRODUCT_DOES_NOT_EXIST"}, status=400)

            # order_product_stocks insert
            added_product = ProductStock.objects.get(product_id=product_id, size=product_size)
            OrderProductStock.objects.update_or_create(
                order         = order,
                product_stock = added_product,
                defaults      = {
                    'quantity' : 1
                }
            )
            
            return JsonResponse({"message": "SUCCESS"}, status=200)
