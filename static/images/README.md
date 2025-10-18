# Images Directory

## Flight Hero Background Image

**File name required:** `flight-hero.jpg`

### Instructions:
1. Place your custom flight/airplane image here
2. Name it exactly: `flight-hero.jpg`
3. Recommended specifications:
   - Format: JPG or PNG
   - Dimensions: 1920x800 pixels (minimum)
   - Size: Under 500KB for optimal loading
   - Content: Airplane, sky, aviation-related imagery

### Alternative File Formats:
If you prefer PNG or other formats, update the CSS in:
`templates/flights/search.html`

Change:
```css
url('{% static "images/flight-hero.jpg" %}')
```

To your format:
```css
url('{% static "images/flight-hero.png" %}')
```

### Current Status:
- Directory created ✓
- CSS updated to use local image ✓
- **ACTION REQUIRED:** Upload your image file here

---

## Adding More Images:

You can add more images to this directory for other pages:
- `hotel-hero.jpg` - For hotel search page
- `car-hero.jpg` - For car rental page
- `home-hero.jpg` - For home page
