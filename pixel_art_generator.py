"""
Pixel Art Generator - Multiple Methods
Supports AI generation, image conversion, and procedural generation
Optimized for RTX 2060 (6GB VRAM)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import numpy as np
import threading
import os
from datetime import datetime

class PixelArtGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Pixel Art Generator")
        self.root.geometry("1000x700")
        self.root.configure(bg="#2b2b2b")
        
        # Variables
        self.current_image = None
        self.ai_available = False
        self.pipe = None
        
        # Check if AI libraries are available
        self.check_ai_availability()
        
        # Setup UI
        self.setup_ui()
        
    def check_ai_availability(self):
        """Check if AI generation is available"""
        try:
            import torch
            from diffusers import StableDiffusionPipeline
            self.ai_available = torch.cuda.is_available()
        except ImportError:
            self.ai_available = False
    
    def setup_ui(self):
        """Setup the user interface"""
        # Title
        title_frame = tk.Frame(self.root, bg="#1e1e1e", height=60)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame, 
            text="🎨 Pixel Art Generator", 
            font=("Arial", 20, "bold"),
            bg="#1e1e1e", 
            fg="#00ff88"
        )
        title_label.pack(pady=10)
        
        # Main container
        main_container = tk.Frame(self.root, bg="#2b2b2b")
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left panel - Controls
        left_panel = tk.Frame(main_container, bg="#1e1e1e", width=350)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Method selection
        method_frame = tk.LabelFrame(
            left_panel, 
            text="Generation Method", 
            bg="#1e1e1e", 
            fg="white",
            font=("Arial", 10, "bold")
        )
        method_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.method_var = tk.StringVar(value="convert")
        
        methods = [
            ("Convert Image to Pixel Art", "convert", True),
            ("AI Generate Pixel Art", "ai", self.ai_available),
            ("Procedural Generation", "procedural", True)
        ]
        
        for text, value, enabled in methods:
            rb = tk.Radiobutton(
                method_frame,
                text=text,
                variable=self.method_var,
                value=value,
                bg="#1e1e1e",
                fg="white" if enabled else "gray",
                selectcolor="#2b2b2b",
                activebackground="#1e1e1e",
                activeforeground="white",
                state=tk.NORMAL if enabled else tk.DISABLED,
                font=("Arial", 9)
            )
            rb.pack(anchor=tk.W, padx=10, pady=5)
        
        # Settings frame
        settings_frame = tk.LabelFrame(
            left_panel,
            text="Settings",
            bg="#1e1e1e",
            fg="white",
            font=("Arial", 10, "bold")
        )
        settings_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Pixel size
        tk.Label(
            settings_frame,
            text="Pixel Size:",
            bg="#1e1e1e",
            fg="white",
            font=("Arial", 9)
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        
        self.pixel_size_var = tk.IntVar(value=8)
        pixel_size_spin = tk.Spinbox(
            settings_frame,
            from_=4,
            to=32,
            textvariable=self.pixel_size_var,
            width=10,
            bg="#2b2b2b",
            fg="white",
            buttonbackground="#3b3b3b"
        )
        pixel_size_spin.grid(row=0, column=1, padx=10, pady=5)
        
        # Color reduction
        tk.Label(
            settings_frame,
            text="Color Palette:",
            bg="#1e1e1e",
            fg="white",
            font=("Arial", 9)
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        
        self.colors_var = tk.IntVar(value=16)
        colors_spin = tk.Spinbox(
            settings_frame,
            from_=8,
            to=256,
            textvariable=self.colors_var,
            width=10,
            bg="#2b2b2b",
            fg="white",
            buttonbackground="#3b3b3b"
        )
        colors_spin.grid(row=1, column=1, padx=10, pady=5)
        
        # AI Prompt (only for AI method)
        self.prompt_frame = tk.LabelFrame(
            left_panel,
            text="AI Prompt",
            bg="#1e1e1e",
            fg="white",
            font=("Arial", 10, "bold")
        )
        self.prompt_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.prompt_text = tk.Text(
            self.prompt_frame,
            height=4,
            bg="#2b2b2b",
            fg="white",
            font=("Arial", 9),
            wrap=tk.WORD
        )
        self.prompt_text.pack(fill=tk.X, padx=10, pady=10)
        self.prompt_text.insert("1.0", "pixel art character, 8-bit style, retro game sprite")
        
        # Buttons
        button_frame = tk.Frame(left_panel, bg="#1e1e1e")
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.load_btn = tk.Button(
            button_frame,
            text="📁 Load Image",
            command=self.load_image,
            bg="#3b3b3b",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.load_btn.pack(fill=tk.X, pady=5)
        
        self.generate_btn = tk.Button(
            button_frame,
            text="✨ Generate Pixel Art",
            command=self.generate_pixel_art,
            bg="#00ff88",
            fg="black",
            font=("Arial", 11, "bold"),
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.generate_btn.pack(fill=tk.X, pady=5)
        
        self.save_btn = tk.Button(
            button_frame,
            text="💾 Save Image",
            command=self.save_image,
            bg="#3b3b3b",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.save_btn.pack(fill=tk.X, pady=5)
        
        # Status
        self.status_label = tk.Label(
            left_panel,
            text="Ready",
            bg="#1e1e1e",
            fg="#00ff88",
            font=("Arial", 9),
            wraplength=330
        )
        self.status_label.pack(side=tk.BOTTOM, pady=10)
        
        # Right panel - Preview
        right_panel = tk.Frame(main_container, bg="#1e1e1e")
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        preview_label = tk.Label(
            right_panel,
            text="Preview",
            bg="#1e1e1e",
            fg="white",
            font=("Arial", 12, "bold")
        )
        preview_label.pack(pady=10)
        
        # Canvas for image preview
        self.canvas = tk.Canvas(
            right_panel,
            bg="#2b2b2b",
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Installation help
        if not self.ai_available:
            help_text = "💡 AI Generation not available.\nTo enable: pip install torch torchvision diffusers transformers accelerate"
            help_label = tk.Label(
                left_panel,
                text=help_text,
                bg="#1e1e1e",
                fg="orange",
                font=("Arial", 8),
                wraplength=330,
                justify=tk.LEFT
            )
            help_label.pack(side=tk.BOTTOM, pady=5)
    
    def load_image(self):
        """Load an image file"""
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                self.current_image = Image.open(file_path).convert("RGB")
                self.display_image(self.current_image)
                self.status_label.config(text=f"Loaded: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {str(e)}")
    
    def generate_pixel_art(self):
        """Generate pixel art based on selected method"""
        method = self.method_var.get()
        
        if method == "convert":
            if self.current_image is None:
                messagebox.showwarning("No Image", "Please load an image first!")
                return
            self.convert_to_pixel_art()
        
        elif method == "ai":
            if not self.ai_available:
                messagebox.showwarning("AI Not Available", 
                    "AI generation requires: torch, diffusers\n\n"
                    "Install with:\npip install torch torchvision diffusers transformers accelerate")
                return
            self.generate_ai_pixel_art()
        
        elif method == "procedural":
            self.generate_procedural_pixel_art()
    
    def convert_to_pixel_art(self):
        """Convert current image to pixel art"""
        self.status_label.config(text="Converting to pixel art...")
        self.generate_btn.config(state=tk.DISABLED)
        
        def process():
            try:
                pixel_size = self.pixel_size_var.get()
                num_colors = self.colors_var.get()
                
                # Resize down
                small_width = self.current_image.width // pixel_size
                small_height = self.current_image.height // pixel_size
                
                small_img = self.current_image.resize(
                    (small_width, small_height),
                    Image.Resampling.NEAREST
                )
                
                # Reduce colors
                small_img = small_img.quantize(colors=num_colors).convert("RGB")
                
                # Scale back up
                pixel_art = small_img.resize(
                    (small_width * pixel_size, small_height * pixel_size),
                    Image.Resampling.NEAREST
                )
                
                self.current_image = pixel_art
                self.root.after(0, lambda: self.display_image(pixel_art))
                self.root.after(0, lambda: self.status_label.config(text="Pixel art created!"))
                self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, lambda: self.generate_btn.config(state=tk.NORMAL))
        
        threading.Thread(target=process, daemon=True).start()
    
    def generate_ai_pixel_art(self):
        """Generate pixel art using AI"""
        self.status_label.config(text="Initializing AI model (this may take a moment)...")
        self.generate_btn.config(state=tk.DISABLED)
        
        def process():
            try:
                import torch
                from diffusers import StableDiffusionPipeline
                
                # Load model if not already loaded
                if self.pipe is None:
                    self.root.after(0, lambda: self.status_label.config(
                        text="Loading AI model... (first time takes longer)"
                    ))
                    
                    # Use a smaller, faster model optimized for pixel art
                    model_id = "stabilityai/stable-diffusion-2-1-base"
                    
                    self.pipe = StableDiffusionPipeline.from_pretrained(
                        model_id,
                        torch_dtype=torch.float16,
                        safety_checker=None
                    )
                    self.pipe = self.pipe.to("cuda")
                    self.pipe.enable_attention_slicing()
                
                self.root.after(0, lambda: self.status_label.config(text="Generating image..."))
                
                prompt = self.prompt_text.get("1.0", tk.END).strip()
                enhanced_prompt = f"{prompt}, pixel art, 8-bit, retro game style, sharp pixels"
                
                # Generate image
                with torch.no_grad():
                    result = self.pipe(
                        enhanced_prompt,
                        num_inference_steps=30,
                        guidance_scale=7.5,
                        height=512,
                        width=512
                    )
                    image = result.images[0]
                
                # Convert to pixel art style
                pixel_size = self.pixel_size_var.get()
                num_colors = self.colors_var.get()
                
                small_width = image.width // pixel_size
                small_height = image.height // pixel_size
                
                small_img = image.resize((small_width, small_height), Image.Resampling.NEAREST)
                small_img = small_img.quantize(colors=num_colors).convert("RGB")
                
                pixel_art = small_img.resize(
                    (small_width * pixel_size, small_height * pixel_size),
                    Image.Resampling.NEAREST
                )
                
                self.current_image = pixel_art
                self.root.after(0, lambda: self.display_image(pixel_art))
                self.root.after(0, lambda: self.status_label.config(text="AI pixel art generated!"))
                self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"AI generation failed: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.generate_btn.config(state=tk.NORMAL))
        
        threading.Thread(target=process, daemon=True).start()
    
    def generate_procedural_pixel_art(self):
        """Generate procedural pixel art (no AI needed)"""
        self.status_label.config(text="Generating procedural pixel art...")
        self.generate_btn.config(state=tk.DISABLED)
        
        def process():
            try:
                pixel_size = self.pixel_size_var.get()
                width, height = 32, 32  # Grid size
                
                # Create random pixel art pattern
                np.random.seed(int(datetime.now().timestamp()))
                
                # Generate symmetric character
                half_width = width // 2
                left_half = np.random.rand(height, half_width, 3)
                
                # Mirror for symmetry
                full_pattern = np.concatenate([left_half, np.fliplr(left_half)], axis=1)
                
                # Threshold to create distinct shapes
                full_pattern = (full_pattern > 0.6).astype(float)
                
                # Add colors
                colors = [
                    [255, 100, 100],  # Red
                    [100, 255, 100],  # Green
                    [100, 100, 255],  # Blue
                    [255, 255, 100],  # Yellow
                    [255, 100, 255],  # Magenta
                    [100, 255, 255],  # Cyan
                ]
                
                color_choice = colors[np.random.randint(0, len(colors))]
                
                for i in range(3):
                    full_pattern[:, :, i] = full_pattern[:, :, i] * color_choice[i]
                
                # Convert to image
                img_array = full_pattern.astype(np.uint8)
                small_img = Image.fromarray(img_array, mode='RGB')
                
                # Scale up
                pixel_art = small_img.resize(
                    (width * pixel_size, height * pixel_size),
                    Image.Resampling.NEAREST
                )
                
                self.current_image = pixel_art
                self.root.after(0, lambda: self.display_image(pixel_art))
                self.root.after(0, lambda: self.status_label.config(text="Procedural pixel art generated!"))
                self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, lambda: self.generate_btn.config(state=tk.NORMAL))
        
        threading.Thread(target=process, daemon=True).start()
    
    def display_image(self, image):
        """Display image on canvas"""
        # Get canvas size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1:
            canvas_width = 600
        if canvas_height <= 1:
            canvas_height = 600
        
        # Resize image to fit canvas while maintaining aspect ratio
        img_copy = image.copy()
        img_copy.thumbnail((canvas_width - 20, canvas_height - 20), Image.Resampling.NEAREST)
        
        # Convert to PhotoImage
        photo = ImageTk.PhotoImage(img_copy)
        
        # Display on canvas
        self.canvas.delete("all")
        self.canvas.create_image(
            canvas_width // 2,
            canvas_height // 2,
            image=photo,
            anchor=tk.CENTER
        )
        
        # Keep reference
        self.canvas.image = photo
    
    def save_image(self):
        """Save the generated pixel art"""
        if self.current_image is None:
            messagebox.showwarning("No Image", "No image to save!")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                self.current_image.save(file_path)
                self.status_label.config(text=f"Saved: {os.path.basename(file_path)}")
                messagebox.showinfo("Success", "Image saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {str(e)}")

def main():
    root = tk.Tk()
    app = PixelArtGenerator(root)
    root.mainloop()

if __name__ == "__main__":
    main()
