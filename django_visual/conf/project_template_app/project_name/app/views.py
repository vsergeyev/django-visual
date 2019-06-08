# -*- coding: utf-8 -*-

from django.shortcuts import render


def index(request):
	"""
	Main page
	"""

	context = {
	}
	return render(request, 'index.html', context)
