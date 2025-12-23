# books/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator
import json
from .models import Book
from .forms import BookForm, BookSearchForm

@login_required
def books_dashboard(request):
    """Books dashboard page"""
    user_books = Book.objects.filter(posted_by=request.user).order_by('-created_at')[:5]
    
    all_books = Book.objects.filter(is_paid=False).order_by('-created_at')[:8]
    
    featured_books = Book.objects.filter(is_featured=True, is_paid=False).order_by('-created_at')[:4]
    
    total_books = Book.objects.filter(posted_by=request.user).count()
    paid_books = Book.objects.filter(posted_by=request.user, is_paid=True).count()
    free_books = Book.objects.filter(posted_by=request.user, is_paid=False).count()
    total_downloads = Book.objects.filter(posted_by=request.user).aggregate(Sum('download_count'))['download_count__sum'] or 0
    
    context = {
        'user_books': user_books,
        'all_books': all_books,
        'featured_books': featured_books,
        'total_books': total_books,
        'paid_books': paid_books,
        'free_books': free_books,
        'total_downloads': total_downloads,
        'page_title': 'Books Library',
    }
    return render(request, 'books/dashboard.html', context)

@login_required
def books_list(request):
    """List all books with search and filter"""
    books = Book.objects.filter(posted_by=request.user).order_by('-created_at')
    
    # Initialize search form
    form = BookSearchForm(request.GET or None)
    
    if form.is_valid():
        search_query = form.cleaned_data.get('search')
        status_filter = form.cleaned_data.get('status')
        
        if search_query:
            books = books.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        if status_filter == 'paid':
            books = books.filter(is_paid=True)
        elif status_filter == 'free':
            books = books.filter(is_paid=False)
        elif status_filter == 'featured':
            books = books.filter(is_featured=True)
    
    # Pagination
    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'books': page_obj,
        'form': form,
        'page_title': 'My Books',
        'total_books': books.count(),
    }
    return render(request, 'books/list.html', context)

@login_required
def books_browse(request):
    """Browse all public books"""
    books = Book.objects.filter(is_paid=False).order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        books = books.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(posted_by__email__icontains=search_query)
        )
    
    # Filter by category if needed
    category = request.GET.get('category', '')
    if category:
        books = books.filter(category=category)
    
    # Pagination
    paginator = Paginator(books, 16)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'books': page_obj,
        'search_query': search_query,
        'page_title': 'Browse Books',
        'total_books': books.count(),
    }
    return render(request, 'books/browse.html', context)

@login_required
def book_create(request):
    """Create a new book"""
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.posted_by = request.user
            book.save()
            messages.success(request, f'Book "{book.title}" created successfully!')
            return redirect('books:list')
    else:
        form = BookForm()
    
    context = {
        'form': form,
        'page_title': 'Add New Book',
    }
    return render(request, 'books/create.html', context)

@login_required
def book_update(request, pk):
    """Update a book"""
    book = get_object_or_404(Book, pk=pk, posted_by=request.user)
    
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, f'Book "{book.title}" updated successfully!')
            return redirect('books:list')
    else:
        form = BookForm(instance=book)
    
    context = {
        'form': form,
        'book': book,
        'page_title': 'Edit Book',
    }
    return render(request, 'books/update.html', context)

@login_required
def book_delete(request, pk):
    """Delete a book"""
    book = get_object_or_404(Book, pk=pk, posted_by=request.user)
    
    if request.method == 'POST':
        title = book.title
        book.delete()
        messages.success(request, f'Book "{title}" deleted successfully!')
        return redirect('books:list')
    
    context = {
        'book': book,
        'page_title': 'Delete Book',
    }
    return render(request, 'books/delete.html', context)

@login_required
def book_detail(request, pk):
    """View book details"""
    book = get_object_or_404(Book, pk=pk)
    
    # Check if user owns the book or if it's free
    if book.is_paid and book.posted_by != request.user:
        messages.error(request, 'This is a paid book. Please purchase to access.')
        return redirect('books:browse')
    
    context = {
        'book': book,
        'page_title': book.title,
    }
    return render(request, 'books/detail.html', context)

@login_required
def book_download(request, pk):
    """Download a book file"""
    book = get_object_or_404(Book, pk=pk)
    
    # Check access permissions
    if book.is_paid and book.posted_by != request.user:
        messages.error(request, 'This is a paid book. Please purchase to download.')
        return redirect('books:browse')
    
    # Increment download count
    book.increment_download_count()
    
    # Serve the file
    response = FileResponse(book.file.open(), as_attachment=True)
    response['Content-Disposition'] = f'attachment; filename="{book.file.name}"'
    
    # Add download message
    messages.success(request, f'Downloading "{book.title}"...')
    
    return response

@login_required
@csrf_exempt
def book_toggle_featured(request, pk):
    """Toggle featured status via AJAX"""
    if request.method == 'POST':
        book = get_object_or_404(Book, pk=pk, posted_by=request.user)
        book.is_featured = not book.is_featured
        book.save()
        
        return JsonResponse({
            'success': True,
            'is_featured': book.is_featured,
            'message': f'Book {"featured" if book.is_featured else "unfeatured"} successfully'
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
@csrf_exempt
def book_toggle_paid(request, pk):
    """Toggle paid status via AJAX"""
    if request.method == 'POST':
        book = get_object_or_404(Book, pk=pk, posted_by=request.user)
        book.is_paid = not book.is_paid
        book.save()
        
        return JsonResponse({
            'success': True,
            'is_paid': book.is_paid,
            'message': f'Book marked as {"paid" if book.is_paid else "free"} successfully'
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})