# -*- coding: utf-8 -*-

from django.db import models


class BlogPost(models.Model):
	"""
	Entry in blog
	"""
	title = models.CharField(max_length=200)
	pub_date = models.DateTimeField(auto_now_add=True)
	text = models.TextField()
