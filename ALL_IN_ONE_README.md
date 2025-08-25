# All-in-One Dashboard Implementation

## Overview
The `/all-in-one` page provides an experimental unified dashboard that combines all three FS-QR services in a single interface using resizable iframes.

## Features

### 🎨 Beautiful UI/UX Design
- **Gradient backgrounds**: Modern gradient designs with glassmorphism effects
- **Resizable panels**: Three iframe panels that can be resized by dragging handles
- **Responsive design**: Adapts to mobile and desktop screen sizes
- **Smooth animations**: Hover effects and transitions for enhanced user experience

### 🔧 Functionality
- **Service integration**: Displays `/fs-qr_menu`, `/group_menu`, and `/note_menu` in separate iframes
- **Resizable interface**: Users can drag resize handles vertically to adjust panel sizes
- **Layout reset**: Button to restore all panels to default sizes
- **Cross-frame interaction**: Each service maintains full functionality within its iframe

### 📱 Responsive Design
- **Desktop**: Full three-panel layout with drag-to-resize functionality
- **Mobile**: Adapted layout with touch-friendly controls
- **Tablet**: Optimized for mid-size screens

## Technical Implementation

### Route
```python
@app.route('/all-in-one')
def all_in_one():
    return render_template('all-in-one.html')
```

### Key Technologies
- **HTML5 & CSS3**: Modern web standards with flexbox layout
- **JavaScript**: Drag-and-drop resizing with smooth animations
- **iframes**: Secure sandboxing of individual services
- **Responsive CSS**: Media queries for different screen sizes

## Usage
1. Navigate to `/all-in-one` (independent page, no links from other pages)
2. View all three services simultaneously
3. Drag the resize handles (⋮⋮⋮) to adjust panel sizes
4. Click "レイアウトリセット" to restore default layout
5. Each service functions normally within its iframe

## Browser Compatibility
- Modern browsers with ES6+ support
- Chrome, Firefox, Safari, Edge
- Mobile browsers

## Note
This is an experimental feature designed for advanced users who want to access multiple services simultaneously. The implementation is independent and does not affect other parts of the application.