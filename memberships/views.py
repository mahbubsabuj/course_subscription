from django.shortcuts import render,redirect
from django.views.generic import ListView
from .models import Membership,UserMembership,Subscription
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.conf import settings
import stripe

def profile_view(request):
    user_membership = get_user_membership(request)
    user_subscription = get_user_subscription(request)
    context = {
        'user_membership' : user_membership,
        'user_subscription':user_subscription
    } 
    return render(request,"memberships/profile.html",context)


def get_user_membership(request):
    user_membership_qs = UserMembership.objects.filter(user = request.user)
    if user_membership_qs.exists():
        return user_membership_qs.first()
    return None

def get_user_subscription(request):
    user_subscription_qs = Subscription.objects.filter(
        user_membership = get_user_membership(request)
    )
    if user_subscription_qs.exists():
        user_subscription = user_subscription_qs.first()
        return user_subscription
    return None
def get_selected_membership(request):
    membership_type = request.session['selected_membership_type']
    selected_membership_qs = Membership.objects.filter(
            membership_type=membership_type
        )
    if selected_membership_qs.exists():
        return selected_membership_qs.first()
    return None


class MembershipSelectView(ListView):
    model = Membership
    def get_context_data(self,*args,**kwargs):
        context = super().get_context_data(**kwargs)
        #print(context)
        current_membership = get_user_membership(self.request)
        context['current_membership'] = str(current_membership.membership)
        return context
    def post(self,request,**kwargs):
        selected_membership_type = request.POST.get('membership_type')
        user_membership = get_user_membership(request)
        user_subscription = get_user_subscription(request)
        selected_membership_qs = Membership.objects.filter(
            membership_type=selected_membership_type
        )
        if selected_membership_qs.exists():
            selected_membership = selected_membership_qs.first()
        
        if user_membership.membership == selected_membership:
            if user_subscription != None:
                messages.info(request, """You already have this membership. Your
                              next payment is due {}""".format('get this value from stripe'))
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        #sessions
        request.session['selected_membership_type'] = selected_membership.membership_type
        return HttpResponseRedirect(reverse('memberships:payment'))

def PaymentView(request):
    user_membership = get_user_membership(request)
    try:
        selected_membership = get_selected_membership(request)
    except:
        return redirect(reverse("memberships:select"))
    publishKey = settings.STRIPE_PUBLISHABLE_KEY
    if request.method == "POST":
        try:
            token = request.POST['stripeToken']
            customer = stripe.Customer.retrieve(user_membership.stripe_customer_id)
            customer.source = token # 4242424242424242
            customer.save()


            subscription = stripe.Subscription.create(
                customer=user_membership.stripe_customer_id,
                items=[
                    { "plan": selected_membership.stripe_plan_id },
                ]
            )

            return redirect(reverse('memberships:update-transactions',
                                    kwargs={
                                        'subscription_id': subscription.id
                                    }))

        except:
            messages.info(request, "Your payment is not sucessful")

    context = {
        'publishKey': publishKey,
        'selected_membership': selected_membership
    }

    return render(request, "memberships/membership_payment.html", context)
# def PaymentView(request):
#     user_membership = get_user_membership(request)
#     selected_membership = get_selected_membership(request)
#     publishKey = settings.STRIPE_PUBLISHABLE_KEY
    
#     if request.method == "POST":
#         try:
#             token = request.POST['stripeToken']
#             subscription = stripe.Subscription.create(customer=user_membership.stripe_customer_id,items=[{"price": selected_membership.stripe_plan_id}],
#             source = token
#             )
#             return redirect(reverse('memberships:update-transactions',kwargs = {
#                 'subscription_id': subscription.id
#             }))
#         except stripe.CardError as e:
#             messages.info(request,"Your Card has declined")


#     context = {
#         'publishKey':publishKey,
#         'selected_membership':selected_membership
#     }
#     return render(request,"memberships/membership_payment.html",context)
def updateTransaction(request,subscription_id):
    user_membership = get_user_membership(request)
    selected_membership = get_selected_membership(request)
    user_membership.membership = selected_membership
    user_membership.save()

    sub,created = Subscription.objects.get_or_create(user_membership=user_membership)
    sub.stripe_subscription_id = subscription_id
    sub.active = True
    sub.save()
    try:
        del request.session['selected_membership_type']
    except:
        pass
    messages.info(request, 'Successfully created {} membership'.format(
        selected_membership))
    return redirect(reverse('memberships:select'))
def cancelSubscription(request):
    user_sub = get_user_subscription(request)
    if user_sub.active == False:
        messages.info(request,"You don't have an active membership")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    sub = stripe.Subscription.retrieve(user_sub.stripe_subscription_id)
    sub.delete()
    user_sub.active = False
    user_sub.save()
    free_membership = Membership.objects.filter(membership_type='Free').first()
    user_membership = get_user_membership(request)
    user_membership.membership = free_membership
    user_membership.save()
    messages.info(request,"Sucessfully Canelled membership")
    return redirect('/memberships/')
    # return HttpResponseRedirect(request.META.get('HTTP_REFERER'))