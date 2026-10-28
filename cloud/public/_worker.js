// Pages invokes the private API Worker internally; the browser uses the same origin.
export default {
  fetch(request, env) {
    return new URL(request.url).pathname.startsWith('/api/')
      ? env.API.fetch(request)
      : env.ASSETS.fetch(request);
  },
};
