test :
	cp ../environment-test ../environment
	coverage run manage.py test -v 2
	coverage report
	cd media/js; npm run test

run_smoketests :
	python smoketests/smoke.py
