# Instalación, operación y recuperación de Mesh

Estado: pendiente de revisión por Calidad y de revisión para compradores. Base del código fuente: `86dc872d71ec2f668174f632092b371f57cf24c0`. Estas instrucciones preliminares no autorizan una instalación en un entorno de cliente. Este candidato no establece un paquete comercial, una versión compatible para compradores, un archivo de pago, un precio, soporte/SLA ni una oferta SaaS alojada.

## Límites de instalación

Use únicamente un paquete futuro con revisión exacta del código fuente, dependencias, registro de integridad, licencia, configuración y reversión, después de superar las puertas normales de publicación. Este candidato no contiene un paquete de comprador cualificado. No use credenciales de producción ni conecte pasarelas reales mientras evalúa este borrador.

Para una revisión aislada del código en un host privado y desechable, la imagen actual declara Python 3.12 y ejecuta Gunicorn como servidor WSGI. `requirements.txt` contiene rangos de versiones. Por eso, los comandos siguientes solo ilustran un entorno controlado de revisión. No crean una instalación de producción reproducible o compatible:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/gunicorn --bind 127.0.0.1:8080 --workers 1 --threads 80 --timeout 0 main:app
```

Mantenga el servicio enlazado a loopback durante esta revisión aislada. No lo exponga a una LAN ni a Internet. No incluya secretos reales, mapas de identidades de clientes, bases de datos ni direcciones de pasarelas. Calidad debe determinar las variables requeridas y fijar las dependencias compatibles antes de que esta guía sea operativa.

El servidor Flask de Mesh y el conector nativo del host son destinos de despliegue distintos. Conserve `openclaw-plugin-progretech-mesh/`, el proveedor Node de Office y el paquete Python del host; instalar el servidor Flask no instala ni cualifica esos conectores. El Dockerfile ejecuta intencionalmente un solo worker porque el estado activo de WebSocket y de sesión es local al proceso. No añada procesos worker ni réplicas sin un diseño de estado compartido revisado por separado.

## Operación

Antes de una publicación para compradores, los operadores necesitan una matriz de configuración exacta y revisada. El código fuente actual lee selectores como `MESH_ENVIRONMENT`, `MESH_PUBLIC_ORIGIN`, `MESH_AUTH_MODE`, `MESH_FIREBASE_*`, `MESH_OWNER_UID_BINDINGS`, `MESH_ACCOUNT_STORE` y `MESH_ACCOUNT_DB`. La existencia de un selector no define un valor seguro ni un perfil de despliegue compatible. Elija valores solo mediante un proceso autorizado que pertenezca al comprador. Guarde los secretos en el gestor de secretos del comprador o en una inyección protegida del entorno de ejecución. No los escriba en el código, historial de shell, tickets, capturas, registros ni esta guía.

`mesh_account_store.py` contiene implementaciones para SQLite y Firestore. El valor predeterminado de la aplicación depende del entorno; las pruebas usan memoria. Calidad debe demostrar el almacenamiento de producción seleccionado, los controles de acceso, durabilidad, copia de seguridad y restauración antes de recomendarlo. La configuración de la cuenta es distinta de las conexiones activas, sockets, eventos y transferencias locales al proceso. Reiniciar el servicio no restaura esas sesiones activas.

La plantilla Cloud Run de esta base es Knative/Google Cloud Run; no acredita Cloud Foundry ni SAP BTP. No se afirma que exista un conector para una instancia SAP ni un perfil de despliegue BTP.

## Recuperación

1. Detenga los cambios y anote la revisión exacta del paquete, versión del esquema de configuración, backend de almacenamiento y hora del fallo. No copie valores secretos en el registro del incidente.
2. Mantenga aislado el servicio afectado. No inscriba ni reconecte una pasarela real como prueba de recuperación.
3. Restaure una copia propiedad del comprador en un entorno de recuperación separado, siguiendo el procedimiento revisado para el backend seleccionado. No sobrescriba la única copia ni restaure configuración no verificada en el servicio activo.
4. Confirme la configuración de cuenta restaurada y los límites de propiedad con identidades sintéticas. Considere perdidos los sockets, sesiones activas, eventos transitorios y transferencias: son locales al proceso y no forman parte de la copia de seguridad.
5. Valide autenticación, separación de propietarios, compatibilidad de conectores y reversión solo en el entorno aislado. Preserve el entorno nativo del host original, sus permisos, cargas de trabajo y credenciales.
6. Vuelva al servicio únicamente mediante un procedimiento futuro aprobado de publicación y recuperación. Este borrador no define comandos de rotación de claves, reversión de producción ni un canal de soporte para compradores.

No elimine las actas originales del proyecto, avisos de licencia, hoja de ruta ni distribuciones de conectores durante la instalación o recuperación. La guía seguirá pendiente hasta que Calidad apruebe las puertas de instalación del paquete exacto, configuración, persistencia, copia/restauración, actualización/reversión, seguridad y documentación localizada.
