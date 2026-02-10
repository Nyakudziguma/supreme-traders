# books/forms.py
from django import forms
from .models import Book

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'description', 'file', 'price', 'is_paid', 'is_featured']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-amber-500 focus:ring-2 focus:ring-amber-200 outline-none transition-all',
                'placeholder': 'Enter book title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all',
                'placeholder': 'Enter book description',
                'rows': 4
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:ring-2 focus:ring-green-200 outline-none transition-all',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'is_paid': forms.CheckboxInput(attrs={
                'class': 'h-5 w-5 text-amber-600 rounded focus:ring-amber-500 border-gray-300'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'h-5 w-5 text-blue-600 rounded focus:ring-blue-500 border-gray-300'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-purple-500 focus:ring-2 focus:ring-purple-200 outline-none transition-all file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-amber-50 file:text-amber-700 hover:file:bg-amber-100',
            'accept': '.pdf,.epub,.mobi,.doc,.docx,.txt'
        })
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (max 50MB)
            if file.size > 50 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 50MB')
            
            # Check file extension
            valid_extensions = ['.pdf', '.epub', '.mobi', '.doc', '.docx', '.txt']
            if not any(file.name.lower().endswith(ext) for ext in valid_extensions):
                raise forms.ValidationError('Unsupported file format. Please upload PDF, EPUB, MOBI, DOC, DOCX, or TXT.')
        
        return file
    
    def clean_price(self):
        price = self.cleaned_data.get('price')
        is_paid = self.data.get('is_paid')  
        
        is_paid = is_paid == 'on'
        
        if is_paid:
            if price is None or price <= 0:
                raise forms.ValidationError('Price must be greater than 0 for paid books.')
            return price
        else:
            if price is None or price <= 0:
                return 0
            return 0

class BookSearchForm(forms.Form):
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'w-full px-4 py-2 rounded-lg border border-gray-300 focus:border-amber-500 focus:ring-2 focus:ring-amber-200 outline-none',
        'placeholder': 'Search books...'
    }))
    
    status = forms.ChoiceField(required=False, choices=[
        ('', 'All Books'),
        ('paid', 'Paid Books'),
        ('free', 'Free Books'),
        ('featured', 'Featured Books'),
    ], widget=forms.Select(attrs={
        'class': 'px-4 py-2 rounded-lg border border-gray-300 focus:border-amber-500 focus:ring-2 focus:ring-amber-200 outline-none'
    }))