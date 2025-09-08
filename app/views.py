from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse


def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")



import pandas as pd
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render
import requests
import os
from django.conf import settings




CLIENT_ID = settings.CLIENT_ID
CLIENT_SECRET = settings.CLIENT_SECRET
REFRESH_TOKEN = settings.REFRESH_TOKEN

def get_amazon_access_token():
    """
    Fetch new access token from Amazon using refresh_token.
    """
    url = "https://api.amazon.com/auth/o2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json().get("access_token")


def upload_asin_file(request):
    rows = None
    error = None

    if request.method == "POST" and request.FILES.get("asin_file"):
        asin_file = request.FILES["asin_file"]

        # Save temporarily
        fs = FileSystemStorage()
        filename = fs.save(asin_file.name, asin_file)
        file_path = fs.path(filename)

        try:
            # Read Excel file
            df = pd.read_excel(file_path)

            if "ASIN" not in df.columns:
                error = "Excel must have an 'ASIN' column"
            else:
                # 1. Get Amazon Access Token
                try:
                    access_token = get_amazon_access_token()
                except Exception as e:
                    error = f"Failed to get access token: {str(e)}"
                    return render(request, "app/upload_asin.html", {"rows": rows, "error": error})

                results = []
                for _, row in df.iterrows():
                    asin = str(row["ASIN"]).strip()
                    if not asin or asin == "nan":
                        continue

                    # 2. Call restrictions API
                    url = "https://sellingpartnerapi-na.amazon.com/listings/2021-08-01/restrictions"
                    params = {
                        "asin": asin,
                        "conditionType": "new_new",
                        "sellerId": "ADT6FGT66RD0L",   # change if dynamic
                        "marketplaceIds": "A2EUQ1WTGCTBG2",
                    }
                    headers = {
                        "accept": "application/json",
                        "x-amz-access-token": access_token,
                    }

                    try:
                        resp = requests.get(url, headers=headers, params=params, timeout=20)
                        resp.raise_for_status()
                        data = resp.json()
                        # print("API Response:", data)
                    except Exception as e:
                        data = {"error": str(e)}

                    restrictions = data.get("restrictions", [])
                    # print("Restrictions:", restrictions)

                    if restrictions:
                        sell_status = "APPLY TO SELL"
                    else:
                        sell_status = "SELL THIS PRODUCT"

                    results.append({
                        "ASIN": asin,
                        "SELL_STATUS": sell_status,
                    })
                    
                # Create updated DataFrame
                result_df = pd.DataFrame(results)
                rows = result_df.to_dict(orient="records")

                # Save results in session for download
                request.session["asin_results"] = rows
                request.session.modified = True

                # Optional: save updated Excel file on server
                base, ext = os.path.splitext(file_path)
                output_path = f"{base}_updated.xlsx"
                if os.path.exists(output_path):
                    os.remove(output_path)
                result_df.to_excel(output_path, index=False)    

        except Exception as e:
            error = str(e)
        finally:
            # Always remove the original uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)

    return render(request, "app/upload_asin.html", {"rows": rows, "error": error})




def download_asin_results(request):
    """Download processed ASIN results as Excel"""
    asin_results = request.session.get("asin_results")
    if not asin_results:
        return HttpResponse("No results to download.", status=400)

    df = pd.DataFrame(asin_results)

    # Create Excel response
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="asin_results.xlsx"'
    df.to_excel(response, index=False)

    return response
