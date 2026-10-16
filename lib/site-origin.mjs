// Canonical public URL comes from deployment configuration, not proxy headers.
export function siteOrigin(request, env=process.env) {
  const configured=env.PUBLIC_URL||env.RENDER_EXTERNAL_URL;
  if(configured){
    const url=new URL(configured);
    if(!['https:','http:'].includes(url.protocol)||url.username||url.password)throw Error('Invalid public site URL');
    return url.origin;
  }
  const protocol=request.socket?.encrypted||env.NODE_ENV==='production'?'https':'http';
  return new URL(`${protocol}://${request.headers.host||'localhost'}`).origin;
}
