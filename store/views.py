from django.shortcuts import render
from django.http import JsonResponse
from django.http import HttpResponse 
import json
import iyzipay
import datetime
from .models import * 
from .utils import cookieCart, cartData, guestOrder
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def store(request):
	data = cartData(request)

	cartItems = data['cartItems']
	order = data['order']
	items = data['items']

	products = Product.objects.all()
	context = {'products':products, 'cartItems':cartItems}
	return render(request, 'store/store.html', context)

@csrf_exempt
def cart(request):
	data = cartData(request)

	cartItems = data['cartItems']
	order = data['order']
	items = data['items']

	context = {'items':items, 'order':order, 'cartItems':cartItems}
	return render(request, 'store/cart.html', context)

@csrf_exempt
def checkout(request):
	data = cartData(request)
	
	cartItems = data['cartItems']
	order = data['order']
	items = data['items']

	context = {'items':items, 'order':order, 'cartItems':cartItems}
	return render(request, 'store/checkout.html', context)

@csrf_exempt
def updateItem(request):
	data = json.loads(request.body)
	productId = data['productId']
	action = data['action']
	print('Action:', action)
	print('Product:', productId)

	customer = request.user.customer
	product = Product.objects.get(id=productId)
	order, created = Order.objects.get_or_create(customer=customer, complete=False)

	orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)

	if action == 'add':
		orderItem.quantity = (orderItem.quantity + 1)
	elif action == 'remove':
		orderItem.quantity = (orderItem.quantity - 1)

	orderItem.save()

	if orderItem.quantity <= 0:
		orderItem.delete()

	return JsonResponse('Item was added', safe=False)



@csrf_exempt
def processOrder(request):    
    transaction_id = datetime.datetime.now().timestamp()
    data = json.loads(request.body)
    #guest = guestOrder(request, data)

    if request.user.is_authenticated:
        customer = request.user.customer
        order, created = Order.objects.get_or_create(customer=customer, complete=False)
    else:
        customer, order = guestOrder(request, data)

    total = float(data['form']['total'])
    order.transaction_id = transaction_id

    if total == order.get_cart_total:
        order.complete = True
    order.save()

    if order.shipping == True:
        ShippingAddress.objects.create(
        customer=customer,
        order=order,
        address=data['shipping']['address'],
        city=data['shipping']['city'],
        state=data['shipping']['state'],
        zipcode=data['shipping']['zipcode'],
        )

    #if customer == 'AnonymousUser':
    #    customer = guest['customer']

    # --------------------------------------------------------
    # Start iyzico processing here 
    # --------------------------------------------------------   
    #
    print("cust name: ",customer.name)
    print("cust email: ",customer.email)
    print("city: ",data['shipping']['city'])

    options = {
        'api_key': "sandbox-mMFmAU9sflXazllrL23bEeCJTHVvL7kh",
        'secret_key': "sandbox-RW0d1D8guLJTMo2PlI51eAzqPSQY8QLz",
        'base_url': iyzipay.base_url
    }

    #payment_card = {
    #    'cardHolderName': 'John Doe',
    #    'cardNumber': '5528790000000008',
    #    'expireMonth': '12',
    #    'expireYear': '2030',
    #    'cvc': '123',
    #    'registerCard': '0'
    #}

    buyer = {
        'id': 'BY789',
        'name': customer.name,
        'surname': customer.name,
        'gsmNumber': '+905350000000',
        'email': customer.email,
        'identityNumber': '74300864791',
        'lastLoginDate': '2015-10-05 12:43:35',
        'registrationDate': '2013-04-21 15:12:09',
        'registrationAddress': data['shipping']['address'],
        'ip': '85.34.78.112',
        'city': data['shipping']['city'],
        'country': data['shipping']['state'],
        'zipCode': data['shipping']['zipcode']
    }


    address = {
        'contactName': customer.name,
        'city': data['shipping']['city'],
        'country': data['shipping']['state'],
        'zipCode': data['shipping']['zipcode'],
        'address': data['shipping']['address'],
    }



    basket_items = []
    total_price = 0
    basket_id_prfx = 'BI10'
    ind = 0
    orderitems = order.orderitem_set.all()
    print("len orders: ", len(orderitems))
    for item in orderitems:
        basket_item = {}
        basket_item['id'] = basket_id_prfx + str(ind)
        basket_item['name'] = item.product.name
        print("prod name: ", item.product.name)
        basket_item['category1'] = 'Collectibles'
        basket_item['category2'] = 'Accessories'
        basket_item['itemType'] = 'PHYSICAL'
        basket_item['price'] = round(item.product.price * item.quantity, 1)
        basket_items.append(basket_item)
        total_price += round (item.product.price * item.quantity, 1)
        ind +=1 

    print(basket_items)

    print('price: ', str(order.get_cart_total))
    print('total calc price: ', str(total_price))
    print('paidPrice: ', str(order.get_cart_total + order.get_cart_total*0.2))
    #        'paymentCard': payment_card,
    request = {
        'locale': 'tr',
        'conversationId': '123456789',
        'price': str(total_price),
        'paidPrice': str(total_price + total_price*0.2),
        'currency': 'TRY',
        'basketId': 'B67832',
        'paymentGroup': 'PRODUCT',

        "callbackUrl": "http://127.0.0.1:8000",
        'installment': '1',
        'buyer': buyer,
        'shippingAddress': address,
        'billingAddress': address,
        'basketItems': basket_items,
    }

    print('request......\n',request)
    checkout_form_initialize = iyzipay.CheckoutFormInitialize().create(request, options)
    form_init = checkout_form_initialize.read().decode('utf-8')
    d = json.loads(form_init)
    print(d)
    print(d['paymentPageUrl'])
    print(d['checkoutFormContent'])
    context = {'iyzipay-checkout-form': d['checkoutFormContent']}
    show = d['checkoutFormContent'] + '<div id="iyzipay-checkout-form" class="popup"></div>'
    
    #return render(request, 'store/iyzico.html', context)
    #return JsonResponse(d['checkoutFormContent'], safe = False)
    #return JsonResponse(form_init, safe = False)
    return JsonResponse(d)

    #return JsonResponse('Payment submitted..', safe=False)


@csrf_exempt
def iyzico(request):
    options = {
    'api_key': "sandbox-mMFmAU9sflXazllrL23bEeCJTHVvL7kh",
    'secret_key': "sandbox-RW0d1D8guLJTMo2PlI51eAzqPSQY8QLz",
    'base_url': iyzipay.base_url
    }


    #------------------
    payment_card = {
        'cardHolderName': 'John Doe',
        'cardNumber': '5528790000000008',
        'expireMonth': '12',
        'expireYear': '2030',
        'cvc': '123',
        'registerCard': '0'
    }

    buyer = {
        'id': 'BY789',
        'name': 'John',
        'surname': 'Doe',
        'gsmNumber': '+905350000000',
        'email': 'email@email.com',
        'identityNumber': '74300864791',
        'lastLoginDate': '2015-10-05 12:43:35',
        'registrationDate': '2013-04-21 15:12:09',
        'registrationAddress': 'Nidakule Goztepe, Merdivenkoy Mah. Bora Sok. No:1',
        'ip': '85.34.78.112',
        'city': 'Istanbul',
        'country': 'Turkey',
        'zipCode': '34732'
    }

    address = {
        'contactName': 'John Doe',
        'city': 'Istanbul',
        'country': 'Turkey',
        'address': 'Nidakule Goztepe, Merdivenkoy Mah. Bora Sok. No:1',
        'zipCode': '34732'
    }

    basket_items = [
        {
            'id': 'BI101',
            'name': 'Binocular',
            'category1': 'Collectibles',
            'category2': 'Accessories',
            'itemType': 'PHYSICAL',
            'price': '0.3'
        },
        {
            'id': 'BI102',
            'name': 'Game code',
            'category1': 'Game',
            'category2': 'Online Game Items',
            'itemType': 'VIRTUAL',
            'price': '0.5'
        },
        {
            'id': 'BI103',
            'name': 'Usb',
            'category1': 'Electronics',
            'category2': 'Usb / Cable',
            'itemType': 'PHYSICAL',
            'price': '0.2'
        },
        {
            'id': 'BI104',
            'name': 'Usb',
            'category1': 'Electronics',
            'category2': 'Usb / Cable',
            'itemType': 'PHYSICAL',
            'price': '0.4'
        }
    ]

    #----------------------

    request = {
        'locale': 'tr',
        'conversationId': '123456789',
        'price': '1.4',
        'paidPrice': '2.68',
        'currency': 'TRY',
        'basketId': 'BI67832',
        'paymentGroup': 'PRODUCT',
        
        "callbackUrl": "http://127.0.0.1:8000/",
        'installment': '1',
        'buyer': buyer,
        'shippingAddress': address,
        'billingAddress': address,
        'basketItems': basket_items,
    }
    print("what is going on.....\n")
    print(".........working request...... \n", request)
    checkout_form_initialize = iyzipay.CheckoutFormInitialize().create(request, options)
    form_init = checkout_form_initialize.read().decode('utf-8')
    d = json.loads(form_init)
    print(d['paymentPageUrl'])
    print(d['checkoutFormContent'])
    context = {'iyzipay-checkout-form': d['checkoutFormContent']}
    show = d['checkoutFormContent'] + '<div id="iyzipay-checkout-form" class="popup"></div>'
    #return render(request, '<html><body> deneme </body></html>')
    #return render(request, 'store/iyzico.html', context)
    #return JsonResponse(d['checkoutFormContent'], safe = False)
    return JsonResponse(d)