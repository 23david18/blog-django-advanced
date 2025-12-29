from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Post
from django.views.generic import ListView
from .forms import EmailPostForm, CommentForm, SearchForm
from django.core.mail import send_mail
from django.views.decorators.http import require_POST
from taggit.models import Tag
from django.db.models import Count
from django.contrib.postgres.search import (SearchVector, SearchQuery, SearchRank)
from django.contrib.postgres.search import TrigramSimilarity

#class PostListView(ListView):
#    queryset = Post.published.all()
#    context_object_name = 'posts'
#    paginate_by = 3
#    template_name = 'blog/post/list.html'

def post_view(request, tag_slug=None):
    post_list = Post.published.all()
    tag = None

    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        post_list = post_list.filter(tags__in=[tag])

    paginator = Paginator(post_list, 3)
    page_number = request.GET.get('page', 1)
    try:
        posts = paginator.page(page_number)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(1)

    context = {
        'posts': posts,
        'tag': tag
    }
    return render(request, 'blog/post/list.html', context)

def post_detail(request, year, month, day, slug):
    post = get_object_or_404(Post,
                            publish__year=year,
                            publish__month=month,
                            publish__day=day,
                            slug=slug,
                            status=Post.Status.PUBLISHED)
    
    # List de comentarios activos para esta publicación
    comments = post.comments.filter(active=True)
    form = CommentForm()
    
    post_tags_ids = post.tags.values_list('id', flat=True)
    similar_posts = Post.published.filter(tags__in=post_tags_ids).exclude(id=post.id)
    similar_posts = similar_posts.annotate(same_tags=Count('tags')).order_by('-same_tags', '-publish')[:4]

    context = {
        'post': post,
        'comments': comments,
        'form': form,
        'similar_posts': similar_posts
    }

    return render(request, 'blog/post/detail.html', context)

def post_share(request, post_id):
    post = get_object_or_404(Post, id=post_id, status=Post.Status.PUBLISHED)

    sent = False
    if request.method == 'POST':
        form = EmailPostForm(data=request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = (f'{cd['name']} ({cd['email']})' f'recommends you read {post.title}')
            message = (
                f'Read {post.title} at {post_url}\n\n {cd['name']} comments: {cd['comments']}'
            )
            send_mail(subject=subject,
                      message=message,
                      from_email=None,
                      recipient_list=[cd['to']])
            sent = True
    else:
        form = EmailPostForm()

    context = {
        'post': post,
        'form': form,
        'sent': sent
    }
    return render(request, 'blog/post/share.html', context)

@require_POST
def post_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id, status=Post.Status.PUBLISHED)
    comment = None
    form = CommentForm(data=request.POST)

    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.save()

    context = {
        'post':post,
        'form':form,
        'comment': comment
    }
    return render(request, 'blog/post/comment.html', context)

def post_search(request):
    form = SearchForm()
    query = request.GET.get('query')
    results = []

    if query:
        form = SearchForm(request.GET)
        if form.is_valid():
            results = (Post.objects.annotate(similarity=TrigramSimilarity('title', query), ).filter(similarity__gt=0.1).order_by('-similarity'))
    
    context = {
        'form': form,
        'query': query,
        'results': results
    }

    return render(request, 'blog/post/search.html', context)