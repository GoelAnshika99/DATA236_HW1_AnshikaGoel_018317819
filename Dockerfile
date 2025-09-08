FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
COPY new_script.js /usr/share/nginx/html/new_script.js
EXPOSE 80