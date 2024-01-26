#!/usr/bin/python

import json, requests, collections, urllib, os
import getpass 

def flatten_headers( headers ):
    for (k, v) in list(headers.items()):
        if isinstance(v, collections.Iterable):
           headers[k] = ','.join(v)

def post_call(session, url, headers, payload ):
	if (headers['Content-Type'] == 'application/x-www-form-urlencoded'):
		r = session.post( url, headers=headers, data=payload, allow_redirects=False)
	elif (headers['Content-Type'] == 'application/json'):
		r = session.post( url, headers=headers, json=payload, allow_redirects=False)

	return r

def get_oauth_token(session, client_id, client_secret, onelogin_endpoint ):
	url = onelogin_endpoint + '/auth/oauth2/token'
	headers = { 'Authorization': ['client_id:'+client_id, 'client_secret:'+client_secret]}
	flatten_headers(headers)
	headers['Content-Type'] = 'application/json'
	payload = { 'grant_type': 'client_credentials' }

	r = post_call(session, url, headers, payload)
	for item in r.json()['data']:
		access_token = item['access_token']
		#print access_token
	
	return access_token

def get_saml_assert(session, access_token, username, password, app_id, subdomain, onelogin_endpoint ):
	url = onelogin_endpoint + '/api/1/saml_assertion'
	headers = { 'Authorization': 'bearer:' + access_token, 'Content-Type':'application/json'}
	payload = { 'username_or_email': username, 'password': password, 'app_id': app_id, 'subdomain': subdomain }
	#print payload
        r = post_call(session, url, headers, payload)
        #print r.text
	saml_assert = r.json()['data']
	#print saml_assert

	return saml_assert

def get_os_token( session, saml_assert, pf9_endpoint ):
	url = pf9_endpoint + '/Shibboleth.sso/SAML2/POST'
	headers = { 'Content-Type':'application/x-www-form-urlencoded'}
	payload = {'SAMLResponse':saml_assert}

	payload = urllib.urlencode(payload)

	r = post_call(session, url, headers, payload)



def get_unscoped_token( session, pf9_endpoint ):
	r = session.get(pf9_endpoint + '/keystone_admin/v3/OS-FEDERATION/identity_providers/IDP1/protocols/saml2/auth')
	#print r.text
	#print r.headers
	os_token = r.headers['X-Subject-Token']
	#print os_token
	return os_token


def get_tenant( session, os_token, tenant, pf9_endpoint ):
	url = pf9_endpoint + '/keystone/v3/OS-FEDERATION/projects'
	headers = { 'X-Auth-Token': os_token }
	r = session.get(url, headers=headers, allow_redirects=False)

	for project in r.json()['projects']:
		if tenant == project['name']:
			tenant_id = project['id']
			#print tenant_id

	return tenant_id


def get_scoped_token(session, os_token, tenant_id, pf9_endpoint ):
	url = pf9_endpoint + '/keystone/v3/auth/tokens?nocatalog'
	headers = { 'Content-Type':'application/json' }
	payload =  {"auth": {"identity": {"methods": ["saml2"],"saml2": {"id": os_token}},"scope": {"project": {"id": tenant_id}}}}
	
	r = post_call(session, url, headers, payload)
	os_token = r.headers['X-Subject-Token']
	print os_token
        with open('token.txt', 'w') as outfile:
		outfile.write(os_token)
                

def main():
	session = requests.Session()
	onelogin_endpoint = 'https://api.us.onelogin.com'
        client_id = 'fb552c1b6c754307c509260f73e488b4ac8ce682a0ba81762d97e9c1514a5d99'
        client_secret = '276b74c97b475b1ca2c35b2c7d8bee3bcda129c22b86c61f5938cad8ae2bb7da'
        app_id = '597062'
        subdomain = 'scality'
        username = "pierre.merle@scality.com"
	password  = getpass.getpass('Enter password : ')
        tenant = "pierre.merle@scality.com"
        pf9_endpoint = 'https://scality.cloud'
	access_token = get_oauth_token(session, client_id, client_secret, onelogin_endpoint)
	saml_assert = get_saml_assert(session, access_token, username, password, app_id, subdomain, onelogin_endpoint)
	get_os_token(session, saml_assert, pf9_endpoint)
	os_token = get_unscoped_token(session, pf9_endpoint)
	tenant_id = get_tenant(session, os_token, tenant, pf9_endpoint)
	get_scoped_token(session, os_token, tenant_id, pf9_endpoint)

main()

