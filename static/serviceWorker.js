


self.addEventListener('install', e => 
{   
    service_worker_url = new URL(location)
    static_path = service_worker_url.searchParams.get('static_path');
    
    files = 
    [
        '/android-chrome-192x192.png',
        '/android-chrome-512x512.png',
        static_path + 'autocomplete.js',
        static_path + 'autocomplete.css',
        static_path + 'Montserrat.woff2',
    ]

    e.waitUntil( caches.open(static_path).then(cache => cache.addAll(files).then(skipWaiting() ) ) ); 

    console.log('[Service Worker] Install');
});

self.addEventListener('activate', e => 
{     
    service_worker_url = new URL(location)
    static_path = service_worker_url.searchParams.get('static_path');

    // delete all caches except the current one whose name is stored in static_path
    e.waitUntil(caches.keys().then(keys => Promise.all(keys.map(key => key != static_path ? caches.delete(key) : true) )).then(keys => clients.claim())); 

    console.log('[Service Worker] Activate ' + static_path) ;
});


self.addEventListener('fetch', e => 
{
    service_worker_url = new URL(location)
    static_path = service_worker_url.searchParams.get('static_path');


    // fetch the response from the network, put it in the cache.  if there's a network error, return the response from the cache
    fetch_url = (url, cached_url = null) =>
    {
        console.log('[Service Worker] fetch ' + url);

        return fetch(url, {redirect: 'follow'})
        .then
        (
                response => caches.open(static_path)
                .then
                (
                    cache => cache.put(cached_url ? cached_url : url, response.clone()).then( () => response)
                )
        )
        .catch
        ( 
            error => caches.match(url)
        )
    }


    request_url = e.request.url;
    
    if(request_url == location.origin + '/') 
    {
        // test first if root page is already in cache, 
        // if not => first time ever the page is called, get airports list from service worker parameters (as existing cookies are not transmitted in Safari when the app is initially installed)
        changed_url = request_url + '?airports=' + service_worker_url.searchParams.get('airports')

        e.respondWith( caches.match(request_url).then( cached_response => fetch_url(!cached_response ? changed_url : request_url, request_url) ) );
    }
    else
        e.respondWith(fetch_url(request_url));
        

});
