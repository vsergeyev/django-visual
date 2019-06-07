# -*- coding: utf-8 -*-

from django.shortcuts import render

from .models import BlogPost


def index(request):
	"""
	Main page
	"""

	posts = BlogPost.objects.all()
	
	context = {
		"posts": posts
	}
	return render(request, 'index.html', context)
