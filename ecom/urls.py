from django.urls import path
from . import views

urlpatterns = [
    path('basket-market/', views.basket_market_view, name='basket-market'),
    path('view-transactions/', views.view_transactions, name='view-transactions'),
    path('recommend-mafia/', views.mafia_recommend_view, name='recommend-mafia'),
] 