# -*- coding: utf-8 -*-
from __future__ import unicode_literals

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
