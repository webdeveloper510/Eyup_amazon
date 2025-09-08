from django.urls import path

from . import views

urlpatterns = [
    path("new", views.index, name="index"),
    path("", views.upload_asin_file, name="upload_asin"),
    
    path("download/", views.download_asin_results, name="download_asin_results"),

]