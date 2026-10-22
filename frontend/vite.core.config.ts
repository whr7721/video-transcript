import {defineConfig} from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import {fileURLToPath,URL} from 'node:url'
export default defineConfig({root:fileURLToPath(new URL('./core',import.meta.url)),publicDir:'public',plugins:[react(),tailwindcss()],base:'/studio/',resolve:{alias:{'@':fileURLToPath(new URL('./src',import.meta.url))}},build:{outDir:'../dist-core',emptyOutDir:true,rollupOptions:{output:{manualChunks(id){if(id.includes('node_modules')){if(id.includes('@tiptap')||id.includes('prosemirror')||id.includes('/marked/'))return 'editor';return 'vendor'}}}}},server:{host:'127.0.0.1',proxy:{'/api':'http://127.0.0.1:8766'}}})
