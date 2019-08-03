# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render

from .models import Item


def index(request):
	"""
	Main page
	"""

	items = Item.objects.all()
	
	context = {
		"items": items
	}
	return render(request, 'index.html', context)


def item_detail(request, item_id):
	"""
	Detail page
	"""
	item = Item.objects.get(pk=item_id)
	context = {
		"item": item
	}
	return render(request, 'item_detail.html', context)


def item_list(request):
	"""
	List of items
	"""
	items = Item.objects.all()
	
	context = {
		"items": items
	}
	return render(request, 'item_list.html', context)
