import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'
export default defineConfig({plugins:[react(),tailwindcss()],base:'/studio/',resolve:{alias:{'@':fileURLToPath(new URL('./src',import.meta.url))}},build:{outDir:'dist',emptyOutDir:true,rollupOptions:{output:{manualChunks(id){if(id.includes('node_modules')){if(/markmap|\/d3[^/]*\/|d3-flextree/.test(id))return 'mindmap-vendor';if(id.includes('@tiptap')||id.includes('prosemirror')||id.includes('/marked/'))return 'editor';return 'vendor'}}}}},server:{proxy:{'/api':'http://127.0.0.1:8765'}}})
