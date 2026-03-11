py -3.12 -m venv .venv

> > .\.venv\Scripts\activate
> > python -m pip install -U pip
> > python -m pip install googletrans==4.0.0rc1
> >
> > No suitable Python runtime found
> > Pass --list (-0) to see all detected environments on your machine
> > or set environment variable PYLAUNCHER_ALLOW_INSTALL to use winget
> > or open the Microsoft Store to the requested version.
> > .\.venv\Scripts\activate : O termo '.\.venv\Scripts\activate' não é reconhecido como nome de
> > cmdlet, função, arquivo de script ou programa operável. Verifique a grafia do nome ou, se um
> > caminho tiver sido incluído, veja se o caminho está correto e tente novamente.
> > No linha:2 caractere:1

- .\.venv\Scripts\activate
- ```
    + CategoryInfo          : ObjectNotFound: (.\.venv\Scripts\activate:String) [], CommandNotFou
   ndException
    + FullyQualifiedErrorId : CommandNotFoundException
  ```

Defaulting to user installation because normal site-packages is not writeable
Requirement already satisfied: pip in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (26.0.1)
Defaulting to user installation because normal site-packages is not writeable
Requirement already satisfied: googletrans==4.0.0rc1 in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (4.0.0rc1)
Requirement already satisfied: httpx==0.13.3 in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from googletrans==4.0.0rc1) (0.13.3)
Requirement already satisfied: certifi in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from httpx==0.13.3->googletrans==4.0.0rc1) (2025.10.5)
Requirement already satisfied: hstspreload in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from httpx==0.13.3->googletrans==4.0.0rc1) (2025.1.1)
Requirement already satisfied: sniffio in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from httpx==0.13.3->googletrans==4.0.0rc1) (1.3.1)
Requirement already satisfied: chardet==3._ in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from httpx==0.13.3->googletrans==4.0.0rc1) (3.0.4)
Requirement already satisfied: idna==2._ in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from httpx==0.13.3->googletrans==4.0.0rc1) (2.10)
Requirement already satisfied: rfc3986<2,>=1.3 in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from httpx==0.13.3->googletrans==4.0.0rc1) (1.5.0)
Requirement already satisfied: httpcore==0.9._ in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from httpx==0.13.3->googletrans==4.0.0rc1) (0.9.1)
Requirement already satisfied: h11<0.10,>=0.8 in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from httpcore==0.9._->httpx==0.13.3->googletrans==4.0.0rc1) (0.9.0)
Requirement already satisfied: h2==3._ in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from httpcore==0.9._->httpx==0.13.3->googletrans==4.0.0rc1) (3.2.0)
Requirement already satisfied: hyperframe<6,>=5.2.0 in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from h2==3._->httpcore==0.9._->httpx==0.13.3->googletrans==4.0.0rc1) (5.2.0)
Requirement already satisfied: hpack<4,>=3.0 in C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages (from h2==3._->httpcore==0.9._->httpx==0.13.3->googletrans==4.0.0rc1) (3.0.0)

python -c "from googletrans import Translator; print(Translator().translate('hello', src='en', dest='pt').text)"
Traceback (most recent call last):
File "<string>", line 1, in <module>
from googletrans import Translator; print(Translator().translate('hello', src='en', dest='pt').text)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages\googletrans\_\_init**.py", line 6, in <module>
from googletrans.client import Translator
File "C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages\googletrans\client.py", line 13, in <module>
import httpx
File "C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages\httpx\_\_init**.py", line 2, in <module>
from .\_api import delete, get, head, options, patch, post, put, request, stream
File "C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages\httpx_api.py", line 3, in <module>
from .\_client import Client, StreamContextManager
File "C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages\httpx_client.py", line 8, in <module>
from .\_auth import Auth, BasicAuth, FunctionAuth
File "C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages\httpx_auth.py", line
10, in <module>
from .\_models import Request, Response
File "C:\Users\miguel.rafael\AppData\Roaming\Python\Python313\site-packages\httpx_models.py", line 1, in <module>
import cgi
ModuleNotFoundError: No module named 'cgi'
PS C:\dev\script-dev>
